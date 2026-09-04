"""
Shared health check library for TRAID Platform services.

Provides standardized health check utilities, response models, and dependency
checking patterns to ensure consistent health monitoring across all services.

Key Features:
- Standardized response format with status, checks, and metadata
- Dependency checking utilities for common services (Redis, HTTP, Database)
- Status aggregation logic (healthy/degraded/unhealthy)
- Performance metrics and timing
- Service-specific extension points
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status levels for services and dependencies."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class DependencyType(str, Enum):
    """Types of dependencies that can be checked."""
    DATABASE = "database"
    REDIS = "redis"
    HTTP_SERVICE = "http_service"
    FILE_SYSTEM = "file_system"
    EXTERNAL_API = "external_api"
    MODEL = "model"
    CUSTOM = "custom"


@dataclass
class DependencyCheck:
    """Configuration for a dependency health check."""
    name: str
    type: DependencyType
    critical: bool = True  # If False, failure only degrades service
    timeout: float = 5.0  # Timeout in seconds
    checker: Callable[[], bool] | None = None  # Custom check function
    url: str | None = None  # For HTTP services
    error_message: str | None = None


class DependencyResult(BaseModel):
    """Result of a dependency health check."""
    name: str
    type: str
    status: HealthStatus
    critical: bool
    response_time_ms: float | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StandardHealthResponse(BaseModel):
    """Standardized health check response format."""
    status: HealthStatus = Field(..., description="Overall service health status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    timestamp: float = Field(
        default_factory=time.time,
        description="Health check timestamp (Unix timestamp)"
    )
    uptime_seconds: float | None = Field(None, description="Service uptime in seconds")
    
    checks: dict[str, str] = Field(
        default_factory=dict,
        description="Simple status map for basic monitoring"
    )
    
    dependencies: list[DependencyResult] = Field(
        default_factory=list,
        description="Detailed dependency check results"
    )
    
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Service-specific metadata"
    )


class HealthChecker:
    """
    Centralized health checker with dependency management.
    
    Provides a consistent interface for performing health checks
    across different service types with configurable dependencies.
    """
    
    def __init__(
        self,
        service_name: str,
        version: str = "1.0.0",
        start_time: float | None = None
    ):
        self.service_name = service_name
        self.version = version
        self.start_time = start_time or time.time()
        self.dependencies: list[DependencyCheck] = []
        self.metadata_providers: list[Callable[[], dict[str, Any]]] = []
    
    def add_dependency(self, dependency: DependencyCheck) -> None:
        """Add a dependency check to the health checker."""
        self.dependencies.append(dependency)
    
    def add_metadata_provider(self, provider: Callable[[], dict[str, Any]]) -> None:
        """Add a metadata provider function."""
        self.metadata_providers.append(provider)
    
    async def check_dependency(self, dep: DependencyCheck) -> DependencyResult:
        """
        Check a single dependency.
        
        Args:
            dep: Dependency configuration
            
        Returns:
            DependencyResult with status and timing information
        """
        start_time = time.time()
        
        try:
            if dep.checker:
                # Custom checker function
                result = await asyncio.wait_for(
                    asyncio.to_thread(dep.checker),
                    timeout=dep.timeout
                )
                success = bool(result)
                metadata = {"custom_check": True}
                
            elif dep.type == DependencyType.HTTP_SERVICE and dep.url:
                # HTTP service check
                success, metadata = await self._check_http_service(dep.url, dep.timeout)
                
            elif dep.type == DependencyType.REDIS:
                # Redis check (requires Redis instance to be passed)
                success = await self._check_redis(dep.timeout)
                metadata = {"connection_type": "redis"}
                
            elif dep.type == DependencyType.DATABASE:
                # Database check (requires DB session to be passed)
                success = await self._check_database(dep.timeout)
                metadata = {"connection_type": "database"}
                
            else:
                # Default: assume healthy if no specific check
                success = True
                metadata = {"default_check": True}
                
            response_time = (time.time() - start_time) * 1000
            
            return DependencyResult(
                name=dep.name,
                type=dep.type.value,
                status=HealthStatus.HEALTHY if success else HealthStatus.UNHEALTHY,
                critical=dep.critical,
                response_time_ms=response_time,
                metadata=metadata
            )
            
        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            return DependencyResult(
                name=dep.name,
                type=dep.type.value,
                status=HealthStatus.UNHEALTHY,
                critical=dep.critical,
                response_time_ms=response_time,
                error="Timeout"
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return DependencyResult(
                name=dep.name,
                type=dep.type.value,
                status=HealthStatus.UNHEALTHY,
                critical=dep.critical,
                response_time_ms=response_time,
                error=str(e)
            )
    
    async def _check_http_service(self, url: str, timeout: float) -> tuple[bool, dict[str, Any]]:
        """Check HTTP service health."""
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url)
                success = response.status_code < 400
                metadata = {
                    "status_code": response.status_code,
                    "url": url
                }
                return success, metadata
        except Exception as e:
            return False, {"error": str(e), "url": url}
    
    async def _check_redis(self, timeout: float) -> bool:
        """Check Redis connectivity. Override in service implementation."""
        # This should be overridden by services that use Redis
        logger.warning("Redis check not implemented - override _check_redis method")
        return True
    
    async def _check_database(self, timeout: float) -> bool:
        """Check database connectivity. Override in service implementation."""
        # This should be overridden by services that use databases
        logger.warning("Database check not implemented - override _check_database method")
        return True
    
    def _aggregate_status(self, dependency_results: list[DependencyResult]) -> HealthStatus:
        """
        Aggregate dependency statuses into overall service status.
        
        Logic:
        - HEALTHY: All critical dependencies healthy
        - DEGRADED: Some non-critical dependencies failing
        - UNHEALTHY: Any critical dependency failing
        """
        critical_failures = [
            r for r in dependency_results 
            if r.critical and r.status == HealthStatus.UNHEALTHY
        ]
        
        if critical_failures:
            return HealthStatus.UNHEALTHY
        
        non_critical_failures = [
            r for r in dependency_results 
            if not r.critical and r.status == HealthStatus.UNHEALTHY
        ]
        
        if non_critical_failures:
            return HealthStatus.DEGRADED
        
        return HealthStatus.HEALTHY
    
    def _collect_metadata(self) -> dict[str, Any]:
        """Collect metadata from all registered providers."""
        metadata = {}
        
        for provider in self.metadata_providers:
            try:
                provider_data = provider()
                if isinstance(provider_data, dict):
                    metadata.update(provider_data)
            except Exception as e:
                logger.warning(f"Metadata provider failed: {e}")
        
        return metadata
    
    async def check_health(self) -> StandardHealthResponse:
        """
        Perform comprehensive health check.
        
        Returns:
            StandardHealthResponse with aggregated status and dependency results
        """
        # Check all dependencies concurrently
        dependency_tasks = [
            self.check_dependency(dep) for dep in self.dependencies
        ]
        
        dependency_results = []
        if dependency_tasks:
            dependency_results = await asyncio.gather(*dependency_tasks, return_exceptions=True)
            
            # Handle any exceptions from dependency checks
            processed_results = []
            for i, result in enumerate(dependency_results):
                if isinstance(result, Exception):
                    dep = self.dependencies[i]
                    processed_results.append(
                        DependencyResult(
                            name=dep.name,
                            type=dep.type.value,
                            status=HealthStatus.UNHEALTHY,
                            critical=dep.critical,
                            error=f"Check failed: {str(result)}"
                        )
                    )
                else:
                    processed_results.append(result)
            
            dependency_results = processed_results
        
        # Aggregate overall status
        overall_status = self._aggregate_status(dependency_results)
        
        # Create simple checks map for basic monitoring compatibility
        checks = {
            dep.name: dep.status.value for dep in dependency_results
        }
        
        # Collect metadata
        metadata = self._collect_metadata()
        
        # Calculate uptime
        uptime_seconds = time.time() - self.start_time
        
        return StandardHealthResponse(
            status=overall_status,
            service=self.service_name,
            version=self.version,
            uptime_seconds=uptime_seconds,
            checks=checks,
            dependencies=dependency_results,
            metadata=metadata
        )


# Convenience functions for common dependency types

def create_http_dependency(
    name: str,
    url: str,
    critical: bool = True,
    timeout: float = 5.0
) -> DependencyCheck:
    """Create an HTTP service dependency check."""
    return DependencyCheck(
        name=name,
        type=DependencyType.HTTP_SERVICE,
        critical=critical,
        timeout=timeout,
        url=url
    )


def create_redis_dependency(
    name: str = "redis",
    critical: bool = True,
    timeout: float = 3.0
) -> DependencyCheck:
    """Create a Redis dependency check."""
    return DependencyCheck(
        name=name,
        type=DependencyType.REDIS,
        critical=critical,
        timeout=timeout
    )


def create_database_dependency(
    name: str = "database",
    critical: bool = True,
    timeout: float = 5.0
) -> DependencyCheck:
    """Create a database dependency check."""
    return DependencyCheck(
        name=name,
        type=DependencyType.DATABASE,
        critical=critical,
        timeout=timeout
    )


def create_custom_dependency(
    name: str,
    checker: Callable[[], bool],
    critical: bool = True,
    timeout: float = 5.0
) -> DependencyCheck:
    """Create a custom dependency check."""
    return DependencyCheck(
        name=name,
        type=DependencyType.CUSTOM,
        critical=critical,
        timeout=timeout,
        checker=checker
    )