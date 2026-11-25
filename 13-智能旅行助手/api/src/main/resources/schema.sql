-- 智能旅行助手 · 表结构（MySQL 8+）
-- 初始化：mysql -uroot -p trip_planner < api/src/main/resources/schema.sql

CREATE TABLE IF NOT EXISTS trip_job (
  id            CHAR(26)     NOT NULL PRIMARY KEY COMMENT '任务ID（ULID 风格）',
  anon_id       VARCHAR(64)  NOT NULL COMMENT '匿名会话标识',
  status        VARCHAR(16)  NOT NULL COMMENT 'PENDING/RUNNING/SUCCEEDED/FAILED',
  request_json  JSON         NOT NULL,
  error_code    VARCHAR(32)  NULL,
  error_message VARCHAR(512) NULL,
  created_at    DATETIME(3)  NOT NULL,
  updated_at    DATETIME(3)  NOT NULL,
  KEY idx_anon_created (anon_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS trip (
  id          CHAR(26)    NOT NULL PRIMARY KEY,
  job_id      CHAR(26)    NOT NULL,
  anon_id     VARCHAR(64) NOT NULL,
  city        VARCHAR(64) NOT NULL,
  start_date  DATE        NOT NULL,
  end_date    DATE        NOT NULL,
  plan_json   JSON        NOT NULL COMMENT '完整行程（TripPlan）',
  budget_json JSON        NOT NULL COMMENT 'Java 计算的分项与合计（单位：分）',
  version     INT         NOT NULL DEFAULT 1,
  created_at  DATETIME(3) NOT NULL,
  updated_at  DATETIME(3) NOT NULL,
  UNIQUE KEY uk_job (job_id),
  KEY idx_anon (anon_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 进度事件：支撑 SSE 的 Last-Event-ID 断线续传
CREATE TABLE IF NOT EXISTS trip_event (
  job_id       CHAR(26)    NOT NULL,
  seq          INT         NOT NULL,
  type         VARCHAR(24) NOT NULL,
  payload_json JSON        NOT NULL,
  created_at   DATETIME(3) NOT NULL,
  PRIMARY KEY (job_id, seq)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
