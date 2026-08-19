-- Ensure georag user can connect from both % and localhost (pymysql uses 127.0.0.1 = localhost)
CREATE USER IF NOT EXISTS 'georag'@'localhost' IDENTIFIED WITH mysql_native_password BY 'georag_pass';
GRANT ALL PRIVILEGES ON georag.* TO 'georag'@'localhost';

ALTER USER IF EXISTS 'georag'@'%' IDENTIFIED WITH mysql_native_password BY 'georag_pass';
GRANT ALL PRIVILEGES ON georag.* TO 'georag'@'%';

FLUSH PRIVILEGES;
