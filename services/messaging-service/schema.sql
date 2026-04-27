CREATE DATABASE IF NOT EXISTS messaging_core;
USE messaging_core;

CREATE TABLE IF NOT EXISTS threads (
  thread_id       VARCHAR(50) NOT NULL,
  last_message_at DATETIME,
  created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (thread_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS thread_participants (
  id           INT          NOT NULL AUTO_INCREMENT,
  thread_id    VARCHAR(50)  NOT NULL,
  user_id      VARCHAR(50)  NOT NULL,
  unread_count INT          NOT NULL DEFAULT 0,
  joined_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_thread_user (thread_id, user_id),
  KEY idx_tp_user (user_id),
  CONSTRAINT fk_tp_thread FOREIGN KEY (thread_id)
    REFERENCES threads (thread_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS connections (
  connection_id VARCHAR(50)  NOT NULL,
  requester_id  VARCHAR(50)  NOT NULL,
  receiver_id   VARCHAR(50)  NOT NULL,
  status        ENUM('pending','accepted','rejected','withdrawn') NOT NULL DEFAULT 'pending',
  requested_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (connection_id),
  UNIQUE KEY uq_connection_pair (requester_id, receiver_id),
  KEY idx_conn_receiver (receiver_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
