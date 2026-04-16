"""
FindMyTaste Deep Linking Examples

This file contains practical examples of how to use the deep linking system
in various scenarios within your Django application.
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.urls import reverse
from helpers.deep_linking import DeepLinkManager
from helpers.deep_link_utils import detect_mobile_platform
from helpers.deep_link_analytics import DeepLinkAnalytics


def share_product_example(request, product_id):
    """
    Example: Generate shareable links for a product
    """
    manager = DeepLinkManager()
    
    # Generate links for all platforms
    links = {
        'ios': manager.generate_deep_link('product_detail', platform='ios', product_id=product_id),
        'android': manager.generate_deep_link('product_detail', platform='android', product_id=product_id),
        'universal': manager.generate_deep_link('product_detail', platform='universal', product_id=product_id),
    }
    
    # Generate QR code URL
    qr_url = reverse('deep_link:qr_code', args=['product_detail']) + f'?product_id={product_id}'
    
    return JsonResponse({
        'deep_links': links,
        'qr_code_url': qr_url,
        'share_message': f'Check out this amazing product: {links["universal"]}'
    })


def smart_redirect_example(request):
    """
    Example: Smart redirect based on user's device
    """
    # Detect user's platform
    platform_info = detect_mobile_platform(request)
    manager = DeepLinkManager()
    
    # Get the route from query parameters
    route = request.GET.get('route', 'marketplace')
    params = {k: v for k, v in request.GET.items() if k != 'route'}
    
    if platform_info['is_mobile']:
        if platform_info['is_app']:
            # User is already in the app, redirect to deep link
            deep_link = manager.generate_deep_link(route, platform=platform_info['platform'], **params)
            return redirect(deep_link)
        else:
            # User is on mobile browser, show app bridge
            return redirect(f'/mobile-app-bridge/?route={route}&auto_redirect=true')
    else:
        # User is on desktop, show universal link
        universal_link = manager.generate_deep_link(route, platform='universal', **params)
        return redirect(universal_link)


def marketing_campaign_example(request, campaign_id):
    """
    Example: Track marketing campaign deep links
    """
    manager = DeepLinkManager()
    analytics = DeepLinkAnalytics()
    
    # Get campaign parameters
    source = request.GET.get('source', 'unknown')
    medium = request.GET.get('medium', 'unknown')
    
    # Detect platform
    platform_info = detect_mobile_platform(request)
    
    # Track the click
    analytics.track_click(
        route='marketplace',
        platform=platform_info['platform'],
        request=request,
        campaign_id=campaign_id,
        source=source,
        medium=medium
    )
    
    # Generate appropriate link
    if platform_info['is_mobile']:
        deep_link = manager.generate_deep_link(
            'marketplace',
            platform=platform_info['platform'],
            campaign_id=campaign_id,
            source=source,
            medium=medium
        )
        return redirect(deep_link)
    else:
        # Show landing page with app download options
        return render(request, 'marketing/campaign_landing.html', {
            'campaign_id': campaign_id,
            'ios_link': manager.generate_deep_link('marketplace', platform='ios'),
            'android_link': manager.generate_deep_link('marketplace', platform='android'),
        })


def order_notification_example(request, order_id):
    """
    Example: Deep link from order notification
    """
    manager = DeepLinkManager()
    platform_info = detect_mobile_platform(request)
    
    # Generate order tracking link
    tracking_link = manager.generate_deep_link(
        'order_tracking',
        platform=platform_info['platform'],
        order_id=order_id
    )
    
    if platform_info['is_mobile'] and not platform_info['is_app']:
        # Mobile browser - use app bridge for better UX
        bridge_url = f'/mobile-app-bridge/?route=order_tracking&order_id={order_id}&auto_redirect=true'
        return redirect(bridge_url)
    else:
        # Direct deep link
        return redirect(tracking_link)


def social_sharing_example(request):
    """
    Example: Generate social media sharing links
    """
    manager = DeepLinkManager()
    
    # Get sharing parameters
    route = request.GET.get('route', 'marketplace')
    title = request.GET.get('title', 'Check out FindMyTaste!')
    description = request.GET.get('description', 'Discover amazing food and restaurants')
    
    # Generate universal link for sharing
    share_link = manager.generate_deep_link(route, platform='universal')
    
    # Generate social media URLs
    social_links = {
        'facebook': f'https://www.facebook.com/sharer/sharer.php?u={share_link}',
        'twitter': f'https://twitter.com/intent/tweet?url={share_link}&text={title}',
        'whatsapp': f'https://wa.me/?text={title} {share_link}',
        'telegram': f'https://t.me/share/url?url={share_link}&text={title}',
    }
    
    return JsonResponse({
        'share_link': share_link,
        'social_links': social_links,
        'qr_code': reverse('deep_link:qr_code', args=[route]),
    })


def restaurant_menu_example(request, vendor_id):
    """
    Example: Share restaurant menu with deep linking
    """
    manager = DeepLinkManager()
    
    # Generate vendor profile links
    links = {
        'ios': manager.generate_deep_link('vendor_profile', platform='ios', vendor_id=vendor_id),
        'android': manager.generate_deep_link('vendor_profile', platform='android', vendor_id=vendor_id),
        'universal': manager.generate_deep_link('vendor_profile', platform='universal', vendor_id=vendor_id),
    }
    
    # Generate QR code for table display
    qr_url = reverse('deep_link:qr_code', args=['vendor_profile']) + f'?vendor_id={vendor_id}'
    
    return render(request, 'restaurant/menu_share.html', {
        'vendor_id': vendor_id,
        'deep_links': links,
        'qr_code_url': qr_url,
        'table_qr_message': 'Scan to view our menu on your phone!'
    })


def analytics_dashboard_example(request):
    """
    Example: Display deep link analytics
    """
    analytics = DeepLinkAnalytics()
    
    # Get analytics summary
    summary = analytics.get_analytics_summary()
    
    # Get detailed analytics by route
    route_analytics = {}
    routes = ['marketplace', 'product_detail', 'vendor_profile', 'order_tracking']
    
    for route in routes:
        route_analytics[route] = analytics.get_route_analytics(route)
    
    return render(request, 'analytics/deep_link_dashboard.html', {
        'summary': summary,
        'route_analytics': route_analytics,
    })


def api_deep_link_example(request):
    """
    Example: API endpoint for generating deep links
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        import json
        data = json.loads(request.body)
        
        route = data.get('route')
        platform = data.get('platform', 'universal')
        params = data.get('params', {})
        
        if not route:
            return JsonResponse({'error': 'Route is required'}, status=400)
        
        manager = DeepLinkManager()
        deep_link = manager.generate_deep_link(route, platform=platform, **params)
        
        return JsonResponse({
            'success': True,
            'deep_link': deep_link,
            'platform': platform,
            'route': route,
            'params': params
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def bulk_qr_generation_example(request):
    """
    Example: Generate QR codes for multiple routes/items
    """
    manager = DeepLinkManager()
    
    # Example: Generate QR codes for all products
    products = [
        {'id': 1, 'name': 'Pizza Margherita'},
        {'id': 2, 'name': 'Burger Deluxe'},
        {'id': 3, 'name': 'Pasta Carbonara'},
    ]
    
    qr_codes = []
    for product in products:
        qr_url = reverse('deep_link:qr_code', args=['product_detail'])
        qr_url += f'?product_id={product["id"]}'
        
        qr_codes.append({
            'product': product,
            'qr_url': qr_url,
            'deep_link': manager.generate_deep_link(
                'product_detail',
                platform='universal',
                product_id=product['id']
            )
        })
    
    return render(request, 'admin/bulk_qr_codes.html', {
        'qr_codes': qr_codes
    })


# Template context processor example
def deep_link_context(request):
    """
    Context processor to add deep link utilities to all templates
    """
    manager = DeepLinkManager()
    platform_info = detect_mobile_platform(request)
    
    return {
        'deep_link_manager': manager,
        'platform_info': platform_info,
        'is_mobile': platform_info['is_mobile'],
        'is_app': platform_info['is_app'],
        'platform': platform_info['platform'],
    }