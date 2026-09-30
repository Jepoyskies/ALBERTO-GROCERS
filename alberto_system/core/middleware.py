# core/middleware.py

from django.utils.deprecation import MiddlewareMixin

class NoCacheMiddleware(MiddlewareMixin):
    """
    Middleware to disable browser caching for all pages.
    This ensures that when a user logs out and clicks 'Back', 
    the browser is forced to request the page from the server 
    (which will then deny access), rather than loading a cached snapshot.
    """
    def process_response(self, request, response):
        # Only apply headers to HTML pages (not necessarily API/Static files, though harmless if applied)
        if 'text/html' in response.get('Content-Type', ''):
            response['Cache-Control'] = "no-cache, no-store, must-revalidate, max-age=0"
            response['Pragma'] = "no-cache"
            response['Expires'] = "0"
        return response