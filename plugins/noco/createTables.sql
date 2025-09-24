CREATE TABLE account (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    created_at DATETIME,
    updated_at DATETIME,
    created_by VARCHAR(255),
    updated_by VARCHAR(255),
    nc_order REAL,
    steamId INTEGER,
    account VARCHAR(255),
    nickname VARCHAR(255)
);
CREATE TABLE records (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    created_at DATETIME,
    updated_at DATETIME,
    created_by VARCHAR(255),
    updated_by VARCHAR(255),
    nc_order REAL,
    gameId INTEGER,
    gameName VARCHAR(255),
    userId INTEGER,
    userName VARCHAR(255),
    Link VARCHAR(255),
    submitTime DATE,
    getTime DATE,
    report BOOLEAN DEFAULT '0',
    publisher VARCHAR(255),
    steamId INTEGER
);
CREATE TABLE remain (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    created_at DATETIME,
    updated_at DATETIME,
    created_by VARCHAR(255),
    updated_by VARCHAR(255),
    nc_order REAL,
    gameId INTEGER,
    gameName VARCHAR(255),
    totalCount INTEGER,
    getedCount INTEGER,
    canBeClaimed_1 VARCHAR(255)
);
CREATE TABLE wishlist (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    created_at DATETIME,
    updated_at DATETIME,
    created_by VARCHAR(255),
    updated_by VARCHAR(255),
    nc_order REAL,
    gameId VARCHAR(255),
    gameName VARCHAR(255),
    userId VARCHAR(255),
    userName VARCHAR(255),
    Link VARCHAR(255),
    submitTime VARCHAR(255),
    publisher VARCHAR(255),
    steamId INTEGER
);
