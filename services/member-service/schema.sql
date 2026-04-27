CREATE DATABASE IF NOT EXISTS member_core;
USE member_core;

CREATE TABLE IF NOT EXISTS members (
    member_id         VARCHAR(50)  NOT NULL,
    user_id           VARCHAR(50)  NOT NULL,
    first_name        VARCHAR(100) NOT NULL,
    last_name         VARCHAR(100) NOT NULL,
    email             VARCHAR(255) NOT NULL,
    phone             VARCHAR(30)  DEFAULT NULL,
    city              VARCHAR(100) DEFAULT NULL,
    state             VARCHAR(100) DEFAULT NULL,
    country           VARCHAR(100) NOT NULL DEFAULT 'US',
    headline          VARCHAR(255) DEFAULT NULL,
    about_summary     TEXT         DEFAULT NULL,
    location          VARCHAR(255) DEFAULT NULL,
    profile_photo_url VARCHAR(500) DEFAULT NULL,
    resume_url        VARCHAR(500) DEFAULT NULL,
    resume_text       TEXT         DEFAULT NULL,
    is_deleted        TINYINT(1)   NOT NULL DEFAULT 0,
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (member_id),
    UNIQUE KEY uq_user_id (user_id),
    UNIQUE KEY uq_email   (email),
    INDEX idx_is_deleted  (is_deleted),
    FULLTEXT KEY ft_search (headline, about_summary)
);

CREATE TABLE IF NOT EXISTS member_skills (
    id         BIGINT       NOT NULL AUTO_INCREMENT,
    member_id  VARCHAR(50)  NOT NULL,
    skill_name VARCHAR(100) NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_member_id (member_id),
    INDEX idx_skill     (skill_name)
);

CREATE TABLE IF NOT EXISTS member_experience (
    id           BIGINT       NOT NULL AUTO_INCREMENT,
    member_id    VARCHAR(50)  NOT NULL,
    company      VARCHAR(200) NOT NULL,
    title        VARCHAR(200) NOT NULL,
    start_date   DATE         DEFAULT NULL,
    end_date     DATE         DEFAULT NULL,
    description  TEXT         DEFAULT NULL,
    PRIMARY KEY (id),
    INDEX idx_member_id (member_id)
);

CREATE TABLE IF NOT EXISTS member_education (
    id           BIGINT       NOT NULL AUTO_INCREMENT,
    member_id    VARCHAR(50)  NOT NULL,
    institution  VARCHAR(200) NOT NULL,
    degree       VARCHAR(200) NOT NULL,
    field        VARCHAR(200) DEFAULT NULL,
    start_year   YEAR         DEFAULT NULL,
    end_year     YEAR         DEFAULT NULL,
    PRIMARY KEY (id),
    INDEX idx_member_id (member_id)
);
