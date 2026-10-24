-- =====================================================
-- 1. DATABASE
-- =====================================================

CREATE DATABASE IF NOT EXISTS claims_db
CHARACTER SET utf8mb4;

USE claims_db;


-- =====================================================
-- 2. HOSPITALS
-- =====================================================

CREATE TABLE hospitals (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(120) NOT NULL,
    city VARCHAR(80) NOT NULL,
    network_status BOOL NOT NULL,
    PRIMARY KEY (id)
);


-- =====================================================
-- 3. PLANS
-- =====================================================

CREATE TABLE plans (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(80) NOT NULL,
    covered_treatment_types VARCHAR(100) NOT NULL,
    annual_limit DECIMAL(12,2) NOT NULL,
    deductible DECIMAL(12,2) NOT NULL,
    copay_percent DECIMAL(5,2) NOT NULL,
    PRIMARY KEY (id)
);


-- =====================================================
-- 4. USERS
-- =====================================================

CREATE TABLE users (
    id INT NOT NULL AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    `role` VARCHAR(20) NOT NULL,
    hospital_id INT,
    PRIMARY KEY (id),
    CONSTRAINT ck_user_role
        CHECK (`role` IN (
            'policyholder',
            'hospital',
            'claims_officer',
            'admin'
        )),
    UNIQUE (username),
    FOREIGN KEY (hospital_id) REFERENCES hospitals(id)
);


-- =====================================================
-- 5. POLICIES
-- =====================================================

CREATE TABLE policies (
    id INT NOT NULL AUTO_INCREMENT,
    holder_user_id INT NOT NULL,
    plan_id INT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (holder_user_id) REFERENCES users(id),
    FOREIGN KEY (plan_id) REFERENCES plans(id)
);


-- =====================================================
-- 6. MEMBERS
-- =====================================================

CREATE TABLE members (
    id INT NOT NULL AUTO_INCREMENT,
    policy_id INT NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    relationship VARCHAR(30) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (policy_id) REFERENCES policies(id)
);


-- =====================================================
-- 7. CLAIMS
-- =====================================================

CREATE TABLE claims (
    id INT NOT NULL AUTO_INCREMENT,
    policy_id INT NOT NULL,
    member_id INT NOT NULL,
    hospital_id INT NOT NULL,
    claim_type VARCHAR(20) NOT NULL,
    treatment_type VARCHAR(20) NOT NULL,
    admission_date DATE NOT NULL,
    discharge_date DATE NOT NULL,
    requested_amount DECIMAL(12,2) NOT NULL,
    eligible_amount DECIMAL(12,2),
    description VARCHAR(255) NOT NULL,
    decision_reason VARCHAR(500),
    status VARCHAR(20) NOT NULL,
    officer_user_id INT,
    created_by_user_id INT NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),

    CONSTRAINT ck_claim_amount
        CHECK (requested_amount > 0),

    CONSTRAINT ck_claim_status
        CHECK (status IN (
            'draft',
            'submitted',
            'in_review',
            'more_info',
            'approved',
            'rejected',
            'paid'
        )),

    FOREIGN KEY (policy_id) REFERENCES policies(id),
    FOREIGN KEY (member_id) REFERENCES members(id),
    FOREIGN KEY (hospital_id) REFERENCES hospitals(id),
    FOREIGN KEY (officer_user_id) REFERENCES users(id),
    FOREIGN KEY (created_by_user_id) REFERENCES users(id)
);

CREATE INDEX ix_claims_officer_status
ON claims (officer_user_id, status);

CREATE INDEX ix_claims_policy_status
ON claims (policy_id, status);


-- =====================================================
-- 8. CLAIM DOCUMENTS
-- =====================================================

CREATE TABLE claim_documents (
    id INT NOT NULL AUTO_INCREMENT,
    claim_id INT NOT NULL,
    document_type VARCHAR(30) NOT NULL,
    checklist_status VARCHAR(20) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (claim_id, document_type),
    FOREIGN KEY (claim_id) REFERENCES claims(id)
);


-- =====================================================
-- 9. CLAIM HISTORY
-- =====================================================

CREATE TABLE claim_history (
    id INT NOT NULL AUTO_INCREMENT,
    claim_id INT NOT NULL,
    sequence_no INT NOT NULL,
    from_status VARCHAR(20),
    to_status VARCHAR(20) NOT NULL,
    actor_user_id INT NOT NULL,
    note VARCHAR(500) NOT NULL,
    `timestamp` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE (claim_id, sequence_no),
    FOREIGN KEY (claim_id) REFERENCES claims(id),
    FOREIGN KEY (actor_user_id) REFERENCES users(id)
);

CREATE INDEX ix_history_claim_time
ON claim_history (claim_id, `timestamp`);


-- =====================================================
-- 10. SETTLEMENTS
-- =====================================================

CREATE TABLE settlements (
    id INT NOT NULL AUTO_INCREMENT,
    claim_id INT NOT NULL,
    payee_type VARCHAR(20) NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    recorded_by_user_id INT NOT NULL,
    recorded_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (claim_id),
    FOREIGN KEY (claim_id) REFERENCES claims(id),
    FOREIGN KEY (recorded_by_user_id) REFERENCES users(id)
);


-- =====================================================
-- 11. REMOVE OLD TRIGGERS
-- =====================================================

DROP TRIGGER IF EXISTS after_claim_settlement;
DROP TRIGGER IF EXISTS after_claim_insert;
DROP TRIGGER IF EXISTS after_claim_status_update;
DROP TRIGGER IF EXISTS after_document_status_update;


-- =====================================================
-- 12. INITIAL CLAIM HISTORY TRIGGER
-- =====================================================

DELIMITER $$

CREATE TRIGGER after_claim_insert
AFTER INSERT ON claims
FOR EACH ROW
BEGIN
    INSERT INTO claim_history (
        claim_id,
        sequence_no,
        from_status,
        to_status,
        actor_user_id,
        note,
        `timestamp`
    )
    VALUES (
        NEW.id,
        1,
        NULL,
        NEW.status,
        NEW.created_by_user_id,
        'Initial claim status',
        NOW()
    );
END$$


-- =====================================================
-- 13. CLAIM STATUS CHANGE TRIGGER
-- =====================================================

CREATE TRIGGER after_claim_status_update
AFTER UPDATE ON claims
FOR EACH ROW
BEGIN
    IF NOT (OLD.status <=> NEW.status) THEN
        INSERT INTO claim_history
            (claim_id, sequence_no, from_status, to_status,
             actor_user_id, note, `timestamp`)
        SELECT
            NEW.id,
            COALESCE(MAX(ch.sequence_no), 0) + 1,
            OLD.status,
            NEW.status,
            COALESCE(NEW.officer_user_id, NEW.created_by_user_id),
            CONCAT('Status changed from ', OLD.status, ' to ', NEW.status),
            NOW()
        FROM claim_history AS ch
        WHERE ch.claim_id = NEW.id;
    END IF;
END$$


-- =====================================================
-- 14. DOCUMENT CHECKLIST CHANGE TRIGGER
-- =====================================================

CREATE TRIGGER after_document_status_update
AFTER UPDATE ON claim_documents
FOR EACH ROW
BEGIN
    IF NOT (OLD.checklist_status <=> NEW.checklist_status) THEN
        INSERT INTO claim_history (claim_id,sequence_no,from_status,to_status,actor_user_id,note,`timestamp`)
        SELECT c.id,(SELECT COALESCE(MAX(ch.sequence_no), 0) + 1 FROM claim_history AS ch WHERE ch.claim_id = c.id),c.status,c.status,
			COALESCE(
					c.officer_user_id,
					c.created_by_user_id),
            CONCAT('Document ', NEW.document_type,' changed from ',OLD.checklist_status,' to ', NEW.checklist_status),
            NOW()
        FROM claims AS c
        WHERE c.id = NEW.claim_id;
    END IF;
END$$

DELIMITER ;


-- =====================================================
-- 15. VERIFY TRIGGERS
-- =====================================================

SHOW TRIGGERS FROM claims_db;


-- =====================================================
-- 16. VIEW CLAIM HISTORY
-- =====================================================

SELECT
    claim_id,
    sequence_no,
    from_status,
    to_status,
    actor_user_id,
    note,
    `timestamp`
FROM claim_history
ORDER BY claim_id, sequence_no;


-- =====================================================
-- 17. VIEW SETTLEMENTS
-- =====================================================

SELECT * FROM settlements;




SELECT TRIGGER_NAME, EVENT_OBJECT_TABLE, ACTION_TIMING, EVENT_MANIPULATION
FROM information_schema.TRIGGERS
WHERE TRIGGER_SCHEMA = 'claims_db';

SELECT TRIGGER_NAME, ACTION_STATEMENT
FROM information_schema.TRIGGERS
WHERE TRIGGER_SCHEMA = 'claims_db'
  AND ACTION_STATEMENT LIKE '%old_status%';
  
  DROP TRIGGER claims_db.after_claim_settlement;