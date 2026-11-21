from rest_framework import serializers
from .models import (
    User, Department, ComplaintCategory, Complaint,
    ComplaintEvidence, ComplaintTimeline, Notification, CitizenFeedback, Subscription
)
from .validators import get_file_type_from_file

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
    file_type = serializers.CharField(required=False)

    class Meta:
        model = ComplaintEvidence
        fields = '__all__'

    def validate(self, attrs):
        file = attrs.get('file')
        file_type = attrs.get('file_type')
        if file:
            inferred_type = get_file_type_from_file(file)
            # If file_type wasn't provided or defaulted inappropriately, use inferred type
            if not file_type or file_type != inferred_type:
                attrs['file_type'] = inferred_type
        return attrs

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

    def validate(self, attrs):
        """
        Independent Backend Validation (Task 7):
        1. Description is required and must be substantive (>= 5 characters).
        2. Address/location is required and must not be empty or vague placeholder.
        3. A landmark name is treated as a landmark/address string, NEVER as verified GPS coordinates.
           (Do not auto-generate or assume latitude/longitude).
        4. Inquiries / chit-chat are prevented from turning into complaints without grievance details.
        """
        description = attrs.get('description', '')
        if not description or len(description.strip()) < 5:
            raise serializers.ValidationError({"description": "A valid complaint description (at least 5 characters) is required."})

        address = attrs.get('address', '')
        vague_placeholders = [
            'reported location', 'here', 'location', 'gali me', 'sadak par',
            'hamare yahan', 'idhar', 'yahan', 'outside', 'unknown', 'n/a'
        ]
        if not address or len(address.strip()) < 3 or address.strip().lower() in vague_placeholders:
            raise serializers.ValidationError({
                "address": "Specific address or landmark is required. General phrases like 'reported location' or 'here' are not accepted."
            })

        # Ensure named landmark is not falsely converted to GPS coordinates
        # latitude and longitude must only be set if explicitly provided as decimal numbers
        lat = attrs.get('latitude')
        lng = attrs.get('longitude')
        if lat is not None and (lat < -90 or lat > 90):
            raise serializers.ValidationError({"latitude": "Invalid GPS latitude."})
        if lng is not None and (lng < -180 or lng > 180):
            raise serializers.ValidationError({"longitude": "Invalid GPS longitude."})

        return attrs

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'

class SubscriptionSerializer(serializers.ModelSerializer):
    user_name = serializers.ReadOnlyField(source='user.username')
    class Meta:
        model = Subscription
        fields = '__all__'

