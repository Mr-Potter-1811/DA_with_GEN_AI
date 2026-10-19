-- Part 1 report queries. Expected outputs are copied from the seeded SQLite database.

-- a) Order totals
-- total_orders|total_revenue|avg_order_value
-- 180|99860.2|554.78
SELECT COUNT(*) AS total_orders,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_revenue,
       ROUND(AVG(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS avg_order_value
FROM orders o
JOIN products p ON o.product_id = p.product_id;

-- b) COUNT(*) vs COUNT(rating)
-- row_count|rated_count|unrated_count
-- 180|165|15
SELECT COUNT(*) AS row_count, COUNT(rating) AS rated_count, COUNT(*) - COUNT(rating) AS unrated_count
FROM orders;

-- c1) LEFT JOIN: customers with zero orders
-- customer_id|name
-- C045|Vihaan
SELECT c.customer_id, c.name
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name
HAVING COUNT(o.order_id) = 0;

-- c2) Independent NOT IN verification of the zero-order customer
-- customer_id|name
-- C045|Vihaan
SELECT customer_id, name
FROM customers
WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM orders);

-- d) City return rate > 20%
-- city|total_orders|returned_orders|return_rate_pct
-- Jaipur|19|8|42.1
-- Lucknow|49|15|30.6
-- Bangalore|33|8|24.2
SELECT c.city,
       COUNT(o.order_id) AS total_orders,
       SUM(o.returned) AS returned_orders,
       ROUND(100.0 * SUM(o.returned) / COUNT(o.order_id), 1) AS return_rate_pct
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY c.city
HAVING return_rate_pct > 20
ORDER BY return_rate_pct DESC;

-- e1) Top 5 customer spend. customer_id is the tie-break so tied spend values always return deterministically.
-- customer_id|name|total_spend
-- C043|Reyansh|12920.0
-- C026|Isha|8371.6
-- C008|Meera|4564.6
-- C011|Arjun|4111.0
-- C042|Sanya|3785.0
SELECT c.customer_id, c.name,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o
JOIN products p ON o.product_id = p.product_id
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.name
ORDER BY total_spend DESC, c.customer_id ASC
LIMIT 5;

-- e2) Ranks 3-5 via LIMIT/OFFSET, without re-deriving the top five.
-- customer_id|name|total_spend
-- C008|Meera|4564.6
-- C011|Arjun|4111.0
-- C042|Sanya|3785.0
SELECT c.customer_id, c.name,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o
JOIN products p ON o.product_id = p.product_id
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.name
ORDER BY total_spend DESC, c.customer_id ASC
LIMIT 3 OFFSET 2;

-- f) Category revenue
-- category|order_count|category_revenue
-- Haircare|54|44956.1
-- Skincare|60|27346.0
-- Babycare|30|16805.0
-- PersonalCare|36|10753.1
SELECT p.category,
       COUNT(o.order_id) AS order_count,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS category_revenue
FROM orders o
JOIN products p ON o.product_id = p.product_id
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY p.category
ORDER BY category_revenue DESC;

-- g) LIKE pattern match: names starting with A.
-- customer_id|name
-- C001|Aarav
-- C003|Aditi
-- C004|Ananya
-- C011|Arjun
-- C021|Aryan
-- C030|Anika
-- C031|Aditya
-- C036|Aisha
-- C041|Ayaan
-- C044|Aria
SELECT customer_id, name
FROM customers
WHERE name LIKE 'A%'
ORDER BY customer_id;

-- h) DISTINCT acquisition sources
-- acquisition_source
-- Ad
-- Organic
-- Referral
-- Social
SELECT DISTINCT acquisition_source
FROM customers
ORDER BY acquisition_source;

-- i) ALTER TABLE + CASE update. Run this section once on a fresh schema.
-- Expected output: Gold|28 and Silver|17.
ALTER TABLE customers ADD COLUMN loyalty_tier VARCHAR(10);
UPDATE customers
SET loyalty_tier = CASE WHEN city_tier = 1 THEN 'Gold' ELSE 'Silver' END;
SELECT loyalty_tier, COUNT(*) AS customer_count
FROM customers
GROUP BY loyalty_tier
ORDER BY CASE loyalty_tier WHEN 'Gold' THEN 1 ELSE 2 END;
