
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from account.models import Address, Notification, Profile, Rider, User, Vendor, VendorRating
from vendor.serializers import VendorSerializer

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


class  RiderSerializer(serializers.Serializer):
    class Meta:
        model = Rider
        fields = '__all__'

class UserSerializer(serializers.ModelSerializer):
    staff_profile = ProfileSerializer(read_only=True)  
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'is_active','role',"password",
                 'is_verified', 'created_at', 'updated_at', 'staff_profile']
        

    
    def to_representation(self, instance):
        if instance.role == 'rider':
            representation = super().to_representation(instance)
            rider_obj , created = Rider.objects.get_or_create(user=instance)
            representation['rider'] = RiderSerializer(rider_obj).data
            return representation
        
        elif instance.role == 'vendor':
            representation = super().to_representation(instance)
            rider_obj , created = Vendor.objects.get_or_create(user=instance)
            representation['vendor'] = VendorSerializer(rider_obj).data
            return representation
        return super().to_representation(instance)


    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User.objects.create(**validated_data)
        if password:
            user.set_password(password)
            user.is_verify = True
            user.save()
        return user
    



class UserAddressCreateSerializer(serializers.Serializer):
    country = serializers.CharField(required=False)
    state = serializers.CharField(required=False)
    city = serializers.CharField(required=False)
    address = serializers.CharField()
    location_latitude = serializers.CharField()
    location_longitude = serializers.CharField()


class VendorAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = [
            'country', 
            'state', 
            'city', 
            'address',
            'location_latitude',
            'location_longitude'
        ]
        





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
    password = serializers.CharField(write_only=True)


    # def validate_email(self, value):
    #     if User.objects.filter(email=value.lower()).exists():
    #         raise ValidationError("Email already exists.")
    #     return value
    

    def create(self, validated_data):
        # Create a User object
        user = User.objects.create(
            email=validated_data['email'].lower(),
            phone_number=validated_data['phone_number'],
            full_name=validated_data['full_name'],
            is_verified=True,
        )
        user.set_password(validated_data['password'])
        user.save()
        return user



class RegisterVerifySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6,required=True)
    email = serializers.EmailField(required=True)


class RegisterOTPResedSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)



class RegisterVendorSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=20,required=True)
    phone_number = serializers.CharField(max_length=20,required=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True)


    # def validate_email(self, value):
    #     if User.objects.filter(email=value.lower()).exists():
    #         raise ValidationError("Email already exists.")
    #     return value
    

    def create(self, validated_data):
        # Create a User object
        user = User.objects.create(
            email=validated_data['email'].lower(),
            phone_number=validated_data['phone_number'],
            full_name=validated_data['full_name'],
            is_verified=False
        )
        user.set_password(validated_data['password'])
        user.save()
        # create a vendor object for the user
        vendor , created = Vendor.objects.get_or_create(user=user)
        return user




class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id","title","content","read","created_at"]




class UpdateBankAccountSerializer(serializers.Serializer):
    account_number = serializers.CharField(required=True )
    bank_name = serializers.CharField(required=True )
    bank_code = serializers.CharField(required=True )




class VendorRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorRating
        fields = ['id', 'vendor', 'user', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'created_at', 'user']  # user is set automatically in the view

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value



class VendorAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = [
            'country', 
            'state', 
            'city', 
            'address',
            'location_latitude',
            'location_longitude'
        ]
        



class ProfileImageUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['profile_image']


class BankAccountValidationSerializer(serializers.Serializer):
    bank_code = serializers.CharField(required=True)
    account_number = serializers.CharField(required=True)