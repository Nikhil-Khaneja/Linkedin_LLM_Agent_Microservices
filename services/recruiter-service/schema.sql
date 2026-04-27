CREATE DATABASE IF NOT EXISTS recruiter_core;
USE recruiter_core;

CREATE TABLE IF NOT EXISTS companies (
  company_id    VARCHAR(50)  NOT NULL,
  company_name  VARCHAR(255) NOT NULL,
  company_industry VARCHAR(100),
  company_size  ENUM('1-10','11-50','51-200','201-500','501-1000','1001-5000','5000+'),
  website       VARCHAR(500),
  description   TEXT,
  logo_url      VARCHAR(500),
  is_active     TINYINT(1)   NOT NULL DEFAULT 1,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS recruiters (
  recruiter_id  VARCHAR(50)  NOT NULL,
  user_id       VARCHAR(50)  NOT NULL,
  company_id    VARCHAR(50)  NOT NULL,
  first_name    VARCHAR(100) NOT NULL,
  last_name     VARCHAR(100) NOT NULL,
  email         VARCHAR(255) NOT NULL,
  access_level  ENUM('admin','recruiter','reviewer') NOT NULL DEFAULT 'recruiter',
  is_active     TINYINT(1)   NOT NULL DEFAULT 1,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (recruiter_id),
  UNIQUE KEY uq_recruiters_email (email),
  UNIQUE KEY uq_recruiters_user (user_id),
  KEY idx_recruiters_company (company_id),
  CONSTRAINT fk_recruiters_company FOREIGN KEY (company_id)
    REFERENCES companies (company_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
