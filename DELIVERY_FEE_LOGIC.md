# Delivery Fee Calculation Logic

This document explains how delivery fees are calculated on the platform, accounting for distance, real-time factors, and service costs.

## Core Components

The total amount a customer pays for delivery consists of two main parts:
1.  **Delivery Fee**: The cost of transporting the items from the vendor to the customer.
2.  **Service Fee**: A platform fee to cover technology and operational costs.

**Total Fee = (Delivery Fee + Service Fee)**

---

## 1. Delivery Fee Calculation

The Delivery Fee is calculated using a multi-step process:

### A. Base Fee (Distance-Based)
The calculation starts with a base fee derived from the **Haversine distance** between the vendor and the customer.
- **Tiers**:
    - 0-2 km: ₦1,000 base
    - 2-5 km: ₦1,200 base + ₦80/km extra
    - 5-10 km: ₦1,500 base + ₦100/km extra
    - 10-20 km: ₦2,000 base + ₦120/km extra
    - >20 km: ₦2,500 base + ₦150/km extra

### B. Surge Pricing (Dynamic Multipliers)
The base fee is then multiplied by real-time factors:
- **Peak Hours**: Rush hours (Morning, Lunch, Evening, Late Night) apply multipliers from **1.2x to 1.4x**.
- **Traffic**: Ranging from **1.0x (Free flow)** to **2.0x (Severe)**.
- **Weather**: Ranging from **1.0x (Clear)** to **2.0x (Snow/Severe)**. Rain typically adds **1.2x to 1.5x**.
- **Rider Availability**: **0.9x (High)** to **1.8x (Critical)**.

### C. Surcharges
- **Item Surcharge**: Orders with more than 1 item incur **₦50 per extra item**.
- **Weight Surcharge**: Weight exceeding 2kg incurs **₦100 per extra kg**. 
    - *Note: Product weights are currently passed dynamically during the order process or default to 1kg if not specified.*

### D. Discounts
- **Loyalty Program**: Tiered discounts from **5% (Bronze)** to **20% (Platinum)**.
- **Promotional Offers**: User-specific, category-specific, or platform-wide percentage discounts can be applied.

### E. Min/Max Constraints
The final delivery fee is constrained between **₦500** and **₦10,000**.

---

## 2. Service Fee (Chowdeck Style)

The Service Fee is calculated separately based on the order's value:
- **Rate**: **2.5%** of the order subtotal.
- **Cap**: Maximum of **₦500**.

*Note: This fee ensures platform stability and is separate from the rider's delivery payout.*

---

## 3. System Configurability

All parameters used in these calculations are **fully configurable** via the admin interface without requiring code changes.

### How it works:
- **Database Driven**: The system looks for pricing tiers, multipliers, and thresholds in the `DeliveryConfiguration` table.
- **Fallbacks**: If a specific configuration is missing from the database, the system safely falls back to hardcoded defaults (the ones listed in this document).
- **Caching**: Configurations are cached for **1 hour** to ensure high performance during checkout.

### Configurable Parameters include:
- Base pricing tiers and per-km rates.
- Surge multipliers (Traffic, Weather, Rider Availability).
- Peak hour time slots and multipliers.
- Service fee percentage and maximum cap.
- Surcharge thresholds and rates.

---

## Example Calculation

**Scenario**: 5km delivery, heavy rain, ₦10,000 order value, 2 items.

1.  **Base Fee**: ₦1,200 + (3km * ₦80) = **₦1,440**
2.  **Weather Surge (Heavy Rain)**: ₦1,440 * 1.5 = **₦2,160**
3.  **Item Surcharge**: 1 extra item = **₦50**
4.  **Delivery Fee Subtotal**: ₦2,160 + ₦50 = **₦2,210**
5.  **Service Fee**: 2.5% of ₦10,000 = **₦250**
6.  **Grand Total**: ₦2,210 + ₦250 = **₦2,460**

---

## Implementation Reference
The logic is implemented in `helpers/order_utils.py` under the `calculate_delivery_fee` function.
