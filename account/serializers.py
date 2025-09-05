
from decimal import Decimal
from django.db.models import Avg
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from account.models import Address, FCMToken, Notification, Profile, PushNotificationLog, Rider, RiderRating, User, Vendor, VendorIssueReporting, VendorRating, VirtualAccount
from product.models import Order
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
        fields = ['id',  'country', 'state','city','address','location_latitude','location_longitude','created_at','updated_at']

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['id',  'created_at', 'updated_at']


class RiderInlineUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'is_active', "profile_image","phone_number"]

class  RiderSerializer(serializers.ModelSerializer):
    user = RiderInlineUserSerializer()
    class Meta:
        model = Rider
        fields = '__all__'
        ref_name = 'AccountRiderSerializer'


    def to_representation(self, instance):
        # Access the custom data
        addition_serializer_data = self.context.get('addition_serializer_data')
        
        # Call super to get default representation
        representation = super().to_representation(instance)
        
        # Modify or add data
        if addition_serializer_data:
            if isinstance(addition_serializer_data,dict):
                rider_type = addition_serializer_data.get('rider_type')
                if rider_type == 'marketplace':
                    orders_queryset_count = Order.objects.filter(
                        rider=instance,
                        delivery_status='pending'
                    ).count()
                    representation['ongoing_orders_count'] = orders_queryset_count

                    ratings = RiderRating.objects.filter(rider=instance)
                    overall_rating = ratings.aggregate(avg_rating=Avg('rating'))['avg_rating']
                    if overall_rating is None:
                        overall_rating = Decimal('0.00')
                    else:
                        overall_rating = round(overall_rating, 2)

                    
                    representation['overall_rating'] = overall_rating



        return representation
    


class  RiderDocumentverificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rider
        fields = ['document_status']



class UserSerializer(serializers.ModelSerializer):
    staff_profile = ProfileSerializer(read_only=True)   
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'full_name', 'is_active',
            'role',"password","phone_number","profile_image",
            "bank_account","bank_name","bank_account_name",
            'is_verified', 'created_at', 
            'updated_at', 'staff_profile'
        ]


    def get_profile_image(self, obj:User):
        return obj.get_profile_image()
        

    
    def to_representation(self, instance:User):
        if instance.role == 'rider':
            representation = super().to_representation(instance)
            rider_obj , created = Rider.objects.get_or_create(user=instance)
            print(rider_obj, created) 
            representation['rider'] = RiderSerializer(rider_obj).data
            representation['profile_image'] = instance.get_profile_image()
            return representation
        
        elif instance.role == 'vendor':
            representation = super().to_representation(instance)
            rider_obj , created = Vendor.objects.get_or_create(user=instance)
            representation['vendor'] = VendorSerializer(rider_obj).data
            representation['profile_image'] = instance.get_profile_image()
            return representation
        
        representation = super().to_representation(instance)
        representation['profile_image'] = instance.get_profile_image()
        return representation


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
    address = serializers.CharField(required=True)
    location_latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=True)
    location_longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=True)


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
    user = UserSerializer()
    class Meta:
        model = VendorRating 
        fields = ['id', 'vendor', 'user', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'created_at', 'user']  # user is set automatically in the view

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value


class VendorIssueReportSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    class Meta:
        model = VendorIssueReporting 
        fields = ['id', 'vendor', 'user', 'message', 'created_at']
        read_only_fields = ['id', 'created_at', 'user'] 

class VirtualAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = VirtualAccount
        exclude = ['user','provider_response','customer_reference']




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


class InitiateWithdrawalSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)



class DeliveryLocationCreatSerializer(serializers.Serializer):
    location_latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=True)
    location_longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=True)
    address = serializers.CharField(required=True)


class FCMTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCMToken
        fields = ['token', 'device_id', 'platform']
    
    def create(self, validated_data):
        user = self.context['request'].user
        device_id = validated_data.get('device_id')
        
        # Update existing token or create new one
        token, created = FCMToken.objects.update_or_create(
            user=user,
            device_id=device_id,
            defaults={
                'token': validated_data['token'],
                'platform': validated_data['platform'],
                'is_active': True
            }
        )
        return token



class SendNotificationSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of user IDs to send notification to"
    )
    title = serializers.CharField(max_length=255)
    body = serializers.CharField()
    data = serializers.JSONField(required=False, default=dict)
    image_url = serializers.URLField(required=False)
    topic = serializers.CharField(required=False, help_text="Topic to send notification to")
    
    def validate(self, attrs):
        if not attrs.get('user_ids') and not attrs.get('topic'):
            raise serializers.ValidationError("Either user_ids or topic must be provided")
        return attrs

class NotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushNotificationLog
        fields = ['id', 'title', 'body', 'data', 'status', 'created_at']