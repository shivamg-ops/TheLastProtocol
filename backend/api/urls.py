from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    RegisterView, UserProfileView, DepartmentViewSet,
    ComplaintCategoryViewSet, ComplaintViewSet, AIAnalysisView,
    EvidenceUploadView, AnalyticsViewSet, NotificationViewSet,
    CivicAssistantViewSet, AuthOTPViewSet, HealthCheckView
)

router = DefaultRouter()
router.register(r'auth/register', RegisterView, basename='register')
router.register(r'auth/otp', AuthOTPViewSet, basename='auth-otp')
router.register(r'departments', DepartmentViewSet, basename='departments')
router.register(r'categories', ComplaintCategoryViewSet, basename='categories')
router.register(r'complaints', ComplaintViewSet, basename='complaints')
router.register(r'evidence', EvidenceUploadView, basename='evidence')
router.register(r'ai', AIAnalysisView, basename='ai')
router.register(r'analytics', AnalyticsViewSet, basename='analytics')
router.register(r'notifications', NotificationViewSet, basename='notifications')
router.register(r'assistant', CivicAssistantViewSet, basename='assistant')

urlpatterns = [
    path('', include(router.urls)),
    path('health/', HealthCheckView.as_view({'get': 'ping'}), name='health_ping'),
    path('health/diagnostics/', HealthCheckView.as_view({'get': 'diagnostics'}), name='health_diagnostics'),
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('user/me/', UserProfileView.as_view({'get': 'me'}), name='user_me'),
    path('user/staff-list/', UserProfileView.as_view({'get': 'staff_list'}), name='user_staff_list'),
    # Task 20: Predictive Civic Intelligence & Preventive Action Endpoints
    path('analytics/predictive/trends/', AnalyticsViewSet.as_view({'get': 'predictive_trends'}), name='predictive_trends'),
    path('analytics/predictive/forecast/', AnalyticsViewSet.as_view({'get': 'predictive_forecast'}), name='predictive_forecast'),
    path('analytics/predictive/hotspots/', AnalyticsViewSet.as_view({'get': 'predictive_hotspots'}), name='predictive_hotspots'),
    path('analytics/predictive/recommendations/', AnalyticsViewSet.as_view({'get': 'predictive_recommendations'}), name='predictive_recommendations'),
]

