-- ============================================================
-- History Service DB Schema (vitamin_history)
-- ============================================================

-- intake_supplements: DMS로 users 서비스 current_supplements에서 동기화 (읽기 전용)
CREATE TABLE "intake_supplements" (
    "current_id"             BIGSERIAL    NOT NULL,
    "cognito_id"             VARCHAR(36)  NOT NULL,
    "itk_product_name"       VARCHAR(255) NULL,
    "itk_serving_amount"     INTEGER      NULL,
    "itk_serving_per_day"    INTEGER      NULL,
    "itk_daily_total_amount" INTEGER      NULL,
    "itk_total_quantity"     INTEGER      NULL,
    "is_active"              BOOLEAN      NULL,
    "itk_purchased_dt"       DATE         NULL,
    "itk_estimated_end_dt"   DATE         NULL,
    "created_at"             TIMESTAMPTZ  NULL,
    "updated_at"             TIMESTAMPTZ  NULL,
    CONSTRAINT "PK_INTAKE_SUPPLEMENTS" PRIMARY KEY ("current_id")
);

COMMENT ON TABLE  "intake_supplements"                   IS 'DMS로 users.current_supplements에서 동기화 — 직접 쓰기 금지';
COMMENT ON COLUMN "intake_supplements"."itk_serving_amount"     IS '한번에 2알';
COMMENT ON COLUMN "intake_supplements"."itk_serving_per_day"    IS '1일 총 3번';
COMMENT ON COLUMN "intake_supplements"."itk_daily_total_amount" IS '1일 총 6알';
COMMENT ON COLUMN "intake_supplements"."itk_total_quantity"     IS '총 60알';
COMMENT ON COLUMN "intake_supplements"."itk_purchased_dt"       IS 'YYYY-MM-DD';
COMMENT ON COLUMN "intake_supplements"."itk_estimated_end_dt"   IS 'YYYY-MM-DD';

-- ------------------------------------------------------------

-- intake_item: 영양제 1회 복용 이벤트 (history 앱이 직접 기록)
CREATE TABLE "intake_item" (
    "item_id"    BIGSERIAL    NOT NULL,
    "current_id" BIGINT       NOT NULL,
    "cognito_id" VARCHAR(36)  NULL,
    "intake_dt"  DATE         NULL,
    "created_at" TIMESTAMPTZ  NULL,
    CONSTRAINT "PK_INTAKE_ITEM" PRIMARY KEY ("item_id"),
    CONSTRAINT "FK_INTAKE_ITEM_SUPPLEMENT" FOREIGN KEY ("current_id")
        REFERENCES "intake_supplements" ("current_id")
);

COMMENT ON COLUMN "intake_item"."intake_dt"  IS 'YYYY-MM-DD';
COMMENT ON COLUMN "intake_item"."created_at" IS '섭취한 시각';

-- ------------------------------------------------------------

-- purchase_history: 영양제 구매 이력 (history 앱이 직접 기록)
CREATE TABLE "purchase_history" (
    "purchase_id"    BIGSERIAL    NOT NULL,
    "item_id"        BIGINT       NOT NULL,
    "cognito_id"     VARCHAR(36)  NULL,
    "purchased_dt"   DATE         NULL,
    "total_quantity" INTEGER      NULL,
    "remain_day"     INTEGER      NULL,
    "reminder_sent"  BOOLEAN      NULL,
    "created_at"     TIMESTAMPTZ  NULL,
    "updated_at"     TIMESTAMPTZ  NULL,
    CONSTRAINT "PK_PURCHASE_HISTORY" PRIMARY KEY ("purchase_id"),
    CONSTRAINT "FK_PURCHASE_HISTORY_ITEM" FOREIGN KEY ("item_id")
        REFERENCES "intake_item" ("item_id")
);

COMMENT ON COLUMN "purchase_history"."purchased_dt"   IS 'YYYY-MM-DD';
COMMENT ON COLUMN "purchase_history"."total_quantity" IS '100알';
COMMENT ON COLUMN "purchase_history"."remain_day"     IS '25일';
COMMENT ON COLUMN "purchase_history"."reminder_sent"  IS 'TRUE=발송';
