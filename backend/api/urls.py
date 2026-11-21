from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    RegisterView, UserProfileView, DepartmentViewSet,
    ComplaintCategoryViewSet, ComplaintViewSet, AIAnalysisView,
    EvidenceUploadView, AnalyticsViewSet
)

router = DefaultRouter()
router.register(r'auth/register', RegisterView, basename='register')
router.register(r'departments', DepartmentViewSet, basename='departments')
router.register(r'categories', ComplaintCategoryViewSet, basename='categories')
router.register(r'complaints', ComplaintViewSet, basename='complaints')
router.register(r'evidence', EvidenceUploadView, basename='evidence')
router.register(r'ai', AIAnalysisView, basename='ai')
router.register(r'analytics', AnalyticsViewSet, basename='analytics')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('user/me/', UserProfileView.as_view({'get': 'me'}), name='user_me'),
]

