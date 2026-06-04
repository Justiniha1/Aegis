-- deploy/demo/db/seed_demo.sql
-- Idempotent demo dataset for the Aegis Airflow demo.
-- Re-run this to reset the demo to a known-good, all-checks-pass state.

DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id  INTEGER PRIMARY KEY,
    first_name   TEXT    NOT NULL,
    last_name    TEXT    NOT NULL,
    email        TEXT    NOT NULL,
    signup_date  DATE    NOT NULL,
    country      TEXT    NOT NULL
);

CREATE TABLE orders (
    order_id     INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date   DATE    NOT NULL,
    order_total  NUMERIC(10,2) NOT NULL,
    status       TEXT    NOT NULL
);

-- 30 customers, all with non-null unique emails.
INSERT INTO customers (customer_id, first_name, last_name, email, signup_date, country) VALUES
 (1,'Ada','Lovelace','ada.lovelace@example.com','2024-01-05','UK'),
 (2,'Alan','Turing','alan.turing@example.com','2024-01-06','UK'),
 (3,'Grace','Hopper','grace.hopper@example.com','2024-01-07','US'),
 (4,'Katherine','Johnson','katherine.johnson@example.com','2024-01-08','US'),
 (5,'Dennis','Ritchie','dennis.ritchie@example.com','2024-01-09','US'),
 (6,'Ken','Thompson','ken.thompson@example.com','2024-01-10','US'),
 (7,'Margaret','Hamilton','margaret.hamilton@example.com','2024-01-11','US'),
 (8,'Barbara','Liskov','barbara.liskov@example.com','2024-01-12','US'),
 (9,'Edsger','Dijkstra','edsger.dijkstra@example.com','2024-01-13','NL'),
 (10,'Linus','Torvalds','linus.torvalds@example.com','2024-01-14','FI'),
 (11,'Guido','vanRossum','guido.vanrossum@example.com','2024-01-15','NL'),
 (12,'Tim','BernersLee','tim.bernerslee@example.com','2024-01-16','UK'),
 (13,'Donald','Knuth','donald.knuth@example.com','2024-01-17','US'),
 (14,'John','McCarthy','john.mccarthy@example.com','2024-01-18','US'),
 (15,'Claude','Shannon','claude.shannon@example.com','2024-01-19','US'),
 (16,'Vint','Cerf','vint.cerf@example.com','2024-01-20','US'),
 (17,'Radia','Perlman','radia.perlman@example.com','2024-01-21','US'),
 (18,'Frances','Allen','frances.allen@example.com','2024-01-22','US'),
 (19,'Leslie','Lamport','leslie.lamport@example.com','2024-01-23','US'),
 (20,'Niklaus','Wirth','niklaus.wirth@example.com','2024-01-24','CH'),
 (21,'Andrew','Tanenbaum','andrew.tanenbaum@example.com','2024-01-25','NL'),
 (22,'Bjarne','Stroustrup','bjarne.stroustrup@example.com','2024-01-26','DK'),
 (23,'James','Gosling','james.gosling@example.com','2024-01-27','CA'),
 (24,'Brian','Kernighan','brian.kernighan@example.com','2024-01-28','CA'),
 (25,'Yukihiro','Matsumoto','yukihiro.matsumoto@example.com','2024-01-29','JP'),
 (26,'Anita','Borg','anita.borg@example.com','2024-01-30','US'),
 (27,'Shafi','Goldwasser','shafi.goldwasser@example.com','2024-01-31','US'),
 (28,'Adi','Shamir','adi.shamir@example.com','2024-02-01','IL'),
 (29,'Whitfield','Diffie','whitfield.diffie@example.com','2024-02-02','US'),
 (30,'Martin','Hellman','martin.hellman@example.com','2024-02-03','US');

-- 40 orders, every customer_id references a real customer, totals all > 0.
INSERT INTO orders (order_id, customer_id, order_date, order_total, status) VALUES
 (1,1,'2024-03-01',120.50,'completed'),
 (2,2,'2024-03-01',88.00,'completed'),
 (3,3,'2024-03-02',240.75,'completed'),
 (4,4,'2024-03-02',56.20,'completed'),
 (5,5,'2024-03-03',310.00,'completed'),
 (6,6,'2024-03-03',74.99,'completed'),
 (7,7,'2024-03-04',199.99,'completed'),
 (8,8,'2024-03-04',64.40,'completed'),
 (9,9,'2024-03-05',410.10,'completed'),
 (10,10,'2024-03-05',150.00,'completed'),
 (11,11,'2024-03-06',92.30,'completed'),
 (12,12,'2024-03-06',133.33,'completed'),
 (13,13,'2024-03-07',77.70,'completed'),
 (14,14,'2024-03-07',265.00,'completed'),
 (15,15,'2024-03-08',58.90,'completed'),
 (16,16,'2024-03-08',180.25,'completed'),
 (17,17,'2024-03-09',99.00,'completed'),
 (18,18,'2024-03-09',145.60,'completed'),
 (19,19,'2024-03-10',322.00,'completed'),
 (20,20,'2024-03-10',61.15,'completed'),
 (21,1,'2024-03-11',210.00,'completed'),
 (22,2,'2024-03-11',54.50,'completed'),
 (23,3,'2024-03-12',176.80,'completed'),
 (24,4,'2024-03-12',83.20,'completed'),
 (25,5,'2024-03-13',299.99,'completed'),
 (26,6,'2024-03-13',67.00,'completed'),
 (27,7,'2024-03-14',128.40,'completed'),
 (28,8,'2024-03-14',95.25,'completed'),
 (29,9,'2024-03-15',355.00,'completed'),
 (30,10,'2024-03-15',142.10,'completed'),
 (31,11,'2024-03-16',71.60,'completed'),
 (32,12,'2024-03-16',188.88,'completed'),
 (33,13,'2024-03-17',60.00,'completed'),
 (34,14,'2024-03-17',244.30,'completed'),
 (35,15,'2024-03-18',52.75,'completed'),
 (36,16,'2024-03-18',165.50,'completed'),
 (37,17,'2024-03-19',110.00,'completed'),
 (38,18,'2024-03-19',137.20,'completed'),
 (39,19,'2024-03-20',288.00,'completed'),
 (40,20,'2024-03-20',69.90,'completed');
