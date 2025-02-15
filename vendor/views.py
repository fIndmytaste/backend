from rest_framework import status, generics
from django.db.models import Q
from helpers.permissions import IsVendor
from product.models import Product, VendorCategory
from .serializers import VendorCategorySerializer, ProductSerializer
from helpers.response.response_format import success_response
from drf_yasg.utils import swagger_auto_schema

# Vendor Views

class VendorCategoryView(generics.GenericAPIView):
    """
    View to handle vendor categories.
    - Vendors can retrieve their own categories or create new ones.
    """
    permission_classes = [IsVendor]
    serializer_class = VendorCategorySerializer

    @swagger_auto_schema(
        operation_description="Retrieve a list of vendor categories with optional search functionality.",
        query_serializer=None,
        responses={200: VendorCategorySerializer(many=True)}
    )
    def get(self, request):
        """
        Retrieve a list of vendor categories with optional search functionality.

        Query Parameters:
        - search (str): Search term to filter categories by name or description.

        Returns:
        - A list of vendor categories matching the search query (if provided).
        """
        search_query = request.GET.get('search', None)

        # Filter by vendor (only the vendor's categories)
        query_filter = Q(vendor=request.user)

        if search_query:
            # Add search filter for name and description
            query_filter &= (Q(name__icontains=search_query) | Q(description__icontains=search_query))
        
        # Get the categories filtered by the search query
        categories = VendorCategory.objects.filter(query_filter).order_by('-created_at')

        # Serialize and return the response
        serializer = self.serializer_class(categories, many=True)
        return success_response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new vendor category.",
        request_body=VendorCategorySerializer,
        responses={201: VendorCategorySerializer}
    )
    def post(self, request):
        """
        Create a new vendor category.

        Body Parameters:
        - name (str): The name of the category.
        - description (str): The description of the category.

        Returns:
        - The newly created vendor category.
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(serializer.data, status_code=status.HTTP_201_CREATED)



class ProductsListCreateView(generics.GenericAPIView):
    """
    View to list and create products for a vendor.
    - Vendors can retrieve a list of their products with filters.
    - Vendors can also create new products.
    """
    permission_classes = [IsVendor]
    serializer_class = ProductSerializer

    @swagger_auto_schema(
        operation_description="Retrieve a list of products with optional search and filter parameters.",
        query_serializer=None,
        responses={200: ProductSerializer(many=True)}
    )
    def get(self, request):
        """
        Retrieve a list of products for a vendor with optional search and filters.

        Query Parameters:
        - search (str): Search term to filter products by name or description.
        - category (str): Filter products by category ID.
        - min_price (float): Filter products by minimum price.
        - max_price (float): Filter products by maximum price.
        - is_active (bool): Filter products by their active status (true/false).
        - is_featured (bool): Filter products by their featured status (true/false).

        Returns:
        - A list of products matching the provided filters.
        """
        query_filter = Q()

        # Search functionality
        search_query = request.GET.get('search', None)
        if search_query:
            query_filter &= (Q(name__icontains=search_query) | Q(description__icontains=search_query))

        # Filter by category
        category = request.GET.get('category', None)
        if category:
            query_filter &= Q(category__id=category)

        # Filter by price range
        min_price = request.GET.get('min_price', None)
        max_price = request.GET.get('max_price', None)
        if min_price:
            query_filter &= Q(price__gte=min_price)
        if max_price:
            query_filter &= Q(price__lte=max_price)

        # Filter by whether the product is active
        is_active = request.GET.get('is_active', None)
        if is_active is not None:
            is_active = is_active.lower() in ['true', '1', 't', 'y', 'yes']
            query_filter &= Q(is_active=is_active)

        # Filter by featured products
        is_featured = request.GET.get('is_featured', None)
        if is_featured is not None:
            is_featured = is_featured.lower() in ['true', '1', 't', 'y', 'yes']
            query_filter &= Q(is_featured=is_featured)

        # Apply all the filters to the products queryset
        products = Product.objects.filter(query_filter)

        # Serialize the filtered products
        serializer = ProductSerializer(products, many=True)
        return success_response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new product.",
        request_body=ProductSerializer,
        responses={201: ProductSerializer}
    )
    def post(self, request):
        """
        Create a new product for the vendor.

        Body Parameters:
        - name (str): The name of the product.
        - description (str): The description of the product.
        - price (float): The price of the product.
        - category (int): The ID of the product's category.
        - stock (int): The stock quantity of the product.
        - image (file, optional): The image of the product.
        - is_active (bool): Whether the product is active or not.
        - is_featured (bool): Whether the product is featured or not.

        Returns:
        - The newly created product.
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(serializer.data, status_code=status.HTTP_201_CREATED)



class ProductGetUpdateDeleteView(generics.GenericAPIView):
    """
    View to retrieve, update, and delete a product for a vendor.
    """
    permission_classes = [IsVendor]
    serializer_class = ProductSerializer

    @swagger_auto_schema(
        operation_description="Retrieve a product by its ID.",
        responses={200: ProductSerializer}
    )
    def get(self, request, product_id):
        """
        Retrieve a product by its ID.

        Parameters:
        - product_id (str): The ID of the product to retrieve.

        Returns:
        - The details of the requested product.
        """
        product = Product.objects.get(id=product_id)
        serializer = ProductSerializer(product)
        return success_response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update a product's information.",
        request_body=ProductSerializer,
        responses={200: ProductSerializer}
    )
    def put(self, request, product_id):
        """
        Update a product's information.

        Parameters:
        - product_id (str): The ID of the product to update.
        - Body parameters: Any fields of the product to update (e.g., name, description, price).

        Returns:
        - The updated product.
        """
        product = Product.objects.get(id=product_id)
        serializer = ProductSerializer(product, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(serializer.data)

    @swagger_auto_schema(
        operation_description="Delete a product by its ID.",
        responses={204: 'No Content'}
    )
    def delete(self, request, product_id):
        """
        Delete a product by its ID.

        Parameters:
        - product_id (str): The ID of the product to delete.

        Returns:
        - Success message after deletion.
        """
        product = Product.objects.get(id=product_id)
        product.delete()
        return success_response(status_code=status.HTTP_204_NO_CONTENT)
