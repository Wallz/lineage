import time
import logging
from django.http import HttpResponseServerError
from django.conf import settings

logger = logging.getLogger(__name__)


class RequestTimeoutMiddleware:
    """
    Middleware para detectar e interromper requests que demoram muito tempo
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Timeout padrão de 30 segundos para requests HTTP
        self.timeout = getattr(settings, 'REQUEST_TIMEOUT', 30)
        
    def __call__(self, request):
        start_time = time.time()
        
        response = self.get_response(request)
        
        execution_time = time.time() - start_time
        
        # Log requests que demoram mais que 5 segundos
        if execution_time > 5:
            logger.warning(
                f"Request lento: {request.method} {request.path} "
                f"demorou {execution_time:.2f}s - IP: {self._get_client_ip(request)}"
            )
        
        # Log requests que demoram mais que 15 segundos como erro
        if execution_time > 15:
            logger.error(
                f"Request muito lento: {request.method} {request.path} "
                f"demorou {execution_time:.2f}s - IP: {self._get_client_ip(request)}"
            )
            
        return response
    
    def _get_client_ip(self, request):
        """Obtém o IP real do cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
