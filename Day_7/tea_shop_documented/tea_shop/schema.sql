CREATE DATABASE IF NOT EXISTS tea_shop;

USE tea_shop;


drop DATABASE tea_shop;


drop TABLE orders;
CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_name VARCHAR(50) NOT NULL,
    tea_type VARCHAR(20) NOT NULL,
    prep_seconds INT NOT NULL,
    simulate_failure BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(20) NOT NULL DEFAULT 'placed',
    failure_reason VARCHAR(200),
    ready_at DOUBLE NOT NULL
);

select * from orders;