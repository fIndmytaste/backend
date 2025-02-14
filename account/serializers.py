
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from account.models import Profile, User

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=100)  
    password = serializers.CharField(write_only=True)



class PasswordResetConfirmSerializer(serializers.Serializer):
    new_password = serializers.CharField(required=True)
    confirm_new_password = serializers.CharField(required=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_new_password']:
            raise ValidationError("New passwords do not match.")
        return data


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()



class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['id',  'created_at', 'updated_at']

class UserSerializer(serializers.ModelSerializer):
    staff_profile = ProfileSerializer(read_only=True)  
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'is_active',"password",
                 'is_verified', 'created_at', 'updated_at', 'staff_profile']


    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User.objects.create(**validated_data)
        if password:
            user.set_password(password)
            user.is_verify = True
            user.save()
        return user
    



class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    confirm_new_password = serializers.CharField(required=True)

    def validate(self, data):
        # Check that new passwords match
        if data['new_password'] != data['confirm_new_password']:
            raise ValidationError("New passwords do not match.")
        return data
    
