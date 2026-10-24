-- =====================================================
-- 1. DATABASE
-- =====================================================

CREATE DATABASE IF NOT EXISTS claims_db
CHARACTER SET utf8mb4;

USE claims_db;


-- =====================================================
-- 2. HOSPITALS
-- =====================================================

CREATE TABLE IF NOT EXISTS hospitals (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(120) NOT NULL,
    city VARCHAR(80) NOT NULL,
    network_status BOOL NOT NULL,
    PRIMARY KEY (id)
);


-- =====================================================
-- 3. PLANS
-- =====================================================

CREATE TABLE IF NOT EXISTS plans (
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

CREATE TABLE IF NOT EXISTS users (
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

CREATE TABLE IF NOT EXISTS policies (
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

CREATE TABLE IF NOT EXISTS members (
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

CREATE TABLE IF NOT EXISTS claims (
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
    FOREIGN KEY (created_by_user_id) REFERENCES users(id),

    INDEX ix_claims_officer_status (officer_user_id, status),
    INDEX ix_claims_policy_status (policy_id, status)
);


-- =====================================================
-- 8. CLAIM DOCUMENTS
-- =====================================================

CREATE TABLE IF NOT EXISTS claim_documents (
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

CREATE TABLE IF NOT EXISTS claim_history (
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
    FOREIGN KEY (actor_user_id) REFERENCES users(id),

    INDEX ix_history_claim_time (claim_id, `timestamp`)
);


-- =====================================================
-- 10. SETTLEMENTS
-- =====================================================

CREATE TABLE IF NOT EXISTS settlements (
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
-- 11. THE ONE TRIGGER: every claims.status change writes its history row
-- =====================================================
-- Only this trigger exists. It fires on UPDATE (never on INSERT), so inserting the demo
-- claims with `flask --app app seed` cannot clash with the history rows loaded from the CSV.
-- Flask hands it the actor and the note through two session variables before it changes the
-- status (SET @audit_actor_id = ..., @audit_note = ...); if they are empty it falls back to
-- the claim's officer / creator and a standard note.
-- Everything else in claim_history (draft created/edited, assignment, checklist, merges)
-- is written by the Flask code, because the status does not change in those events.

DROP TRIGGER IF EXISTS after_claim_insert;              -- removed: old versions of this file had it
DROP TRIGGER IF EXISTS after_document_status_update;    -- removed: old versions of this file had it
DROP TRIGGER IF EXISTS after_claim_settlement;          -- removed: old versions of this file had it
DROP TRIGGER IF EXISTS after_claim_status_update;

DELIMITER $$

CREATE TRIGGER after_claim_status_update
AFTER UPDATE ON claims
FOR EACH ROW
BEGIN
    IF NOT (OLD.status <=> NEW.status) THEN
        INSERT INTO claim_history
            (claim_id, sequence_no, from_status, to_status, actor_user_id, note, `timestamp`)
        SELECT NEW.id,
               COALESCE(MAX(sequence_no), 0) + 1,
               OLD.status,
               NEW.status,
               COALESCE(@audit_actor_id, NEW.officer_user_id, NEW.created_by_user_id),
               LEFT(COALESCE(@audit_note,
                             CONCAT('Status changed from ', OLD.status, ' to ', NEW.status)), 500),
               NOW()
        FROM claim_history
        WHERE claim_id = NEW.id;
    END IF;
END$$

DELIMITER ;


-- =====================================================
-- 12. VERIFY THE TRIGGER (should list exactly one: after_claim_status_update)
-- =====================================================

SHOW TRIGGERS FROM claims_db;


-- =====================================================
-- 13. VIEW CLAIM HISTORY
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
-- 14. VIEW SETTLEMENTS
-- =====================================================

SELECT * FROM settlements;
