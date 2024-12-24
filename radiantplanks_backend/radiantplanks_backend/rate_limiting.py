from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
import time

def rate_limit(max_requests: int, time_window: int):
    """
    Decorator to rate limit specific APIs.
    
    :param max_requests: Maximum number of requests allowed in the time window.
    :param time_window: Time window in seconds for rate limiting.
    """
    def decorator(view_func):
        def wrapped_view(self, request, *args, **kwargs):
            # Identify client by IP address
            client_ip = get_client_ip(request)
            cache_key = f"rate-limit:{client_ip}:{request.path}"

            # Get request count and timestamp from cache
            request_count = cache.get(cache_key, {"count": 0, "timestamp": time.time()})
            current_time = time.time()

            # Check if time window has passed
            if current_time - request_count["timestamp"] > time_window:
                # Reset the count if time window is over
                request_count = {"count": 0, "timestamp": current_time}

            if request_count["count"] >= max_requests:
                retry_after = time_window - (current_time - request_count["timestamp"])
                return Response(
                    {
                        "error": "Rate limit exceeded. Try again later.",
                        "retry_after": int(retry_after),
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            # Increment request count and update timestamp
            request_count["count"] += 1
            cache.set(cache_key, request_count, timeout=time_window)

            return view_func(self, request, *args, **kwargs)
        return wrapped_view
    return decorator

def get_client_ip(request):
    """
    Helper to retrieve the client's IP address from the request.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    return request.META.get("REMOTE_ADDR")
