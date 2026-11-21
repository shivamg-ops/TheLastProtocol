from rest_framework import serializers
from .models import (
    User, Department, ComplaintCategory, Complaint,
    ComplaintEvidence, ComplaintTimeline, Notification, CitizenFeedback, Subscription
)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'phone_number', 'preferred_language', 'organization_name', 'address', 'created_at']
        read_only_fields = ['id', 'created_at']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'first_name', 'last_name', 'role', 'phone_number', 'preferred_language', 'organization_name']

    def create(self, validated_data):
        # Restrict public registration to citizen or non-privileged community tiers only
        role = validated_data.get('role', 'citizen')
        if role in ['admin', 'staff']:
            role = 'citizen'

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=role,
            phone_number=validated_data.get('phone_number', ''),
            preferred_language=validated_data.get('preferred_language', 'en'),
            organization_name=validated_data.get('organization_name', '')
        )
        Subscription.objects.create(user=user, tier='free')
        return user

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'

class ComplaintCategorySerializer(serializers.ModelSerializer):
    department_name = serializers.ReadOnlyField(source='department.name')
    class Meta:
        model = ComplaintCategory
        fields = '__all__'

class ComplaintEvidenceSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.ReadOnlyField(source='uploaded_by.username')
    class Meta:
        model = ComplaintEvidence
        fields = '__all__'

class ComplaintTimelineSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.ReadOnlyField(source='performed_by.username')
    class Meta:
        model = ComplaintTimeline
        fields = '__all__'

class CitizenFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = CitizenFeedback
        fields = '__all__'

class ComplaintSerializer(serializers.ModelSerializer):
    citizen_name = serializers.ReadOnlyField(source='citizen.username')
    category_name = serializers.ReadOnlyField(source='category.name')
    department_name = serializers.ReadOnlyField(source='department.name')
    assigned_staff_name = serializers.ReadOnlyField(source='assigned_staff.username')
    evidences = ComplaintEvidenceSerializer(many=True, read_only=True)
    timeline = ComplaintTimelineSerializer(many=True, read_only=True)
    feedback = CitizenFeedbackSerializer(read_only=True)

    class Meta:
        model = Complaint
        fields = '__all__'
        read_only_fields = ['id', 'tracking_id', 'citizen', 'created_at', 'updated_at']

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'

class SubscriptionSerializer(serializers.ModelSerializer):
    user_name = serializers.ReadOnlyField(source='user.username')
    class Meta:
        model = Subscription
        fields = '__all__'

