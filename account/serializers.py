
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from account.models import Address, Notification, Profile, User

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)  
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



class UserAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id',  'country', 'state','city','address','created_at','updated_at']

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
    



class UserAddressCreateSerializer(serializers.Serializer):
    country = serializers.CharField()
    state = serializers.CharField()
    city = serializers.CharField()
    address = serializers.CharField()




class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    confirm_new_password = serializers.CharField(required=True)

    def validate(self, data):
        # Check that new passwords match
        if data['new_password'] != data['confirm_new_password']:
            raise ValidationError("New passwords do not match.")
        return data
    




class RegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=20,required=True)
    phone_number = serializers.CharField(max_length=20,required=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, min_length=8)


    def validate_email(self, value):
        if User.objects.filter(email=value.lower()).exists():
            raise ValidationError("Email already exists.")
        return value
    

    def create(self, validated_data):
        # Create a User object
        user = User.objects.create(
            email=validated_data['email'],
            phone_number=validated_data['phone_number'],
            full_name=validated_data['full_name'],
            is_verified=True,
        )
        user.set_password(validated_data['password'])
        user.save()
        return user



class RegisterVerifySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6,required=True)



class RegisterVendorSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=20,required=True)
    phone_number = serializers.CharField(max_length=20,required=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, min_length=8)


    def validate_email(self, value):
        if User.objects.filter(email=value.lower()).exists():
            raise ValidationError("Email already exists.")
        return value
    

    def create(self, validated_data):
        # Create a User object
        user = User.objects.create(
            email=validated_data['email'],
            phone_number=validated_data['phone_number'],
            full_name=validated_data['full_name'],
            is_verified=False
        )
        user.set_password(validated_data['password'])
        user.save()
        return user




class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id","title","content","read","created_at"]