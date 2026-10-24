-- MySQL 8 schema generated from app/models.py
CREATE DATABASE IF NOT EXISTS claims_db CHARACTER SET utf8mb4;
USE claims_db;


CREATE TABLE hospitals (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(120) NOT NULL, 
	city VARCHAR(80) NOT NULL, 
	network_status BOOL NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE plans (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(80) NOT NULL, 
	covered_treatment_types VARCHAR(100) NOT NULL, 
	annual_limit NUMERIC(12, 2) NOT NULL, 
	deductible NUMERIC(12, 2) NOT NULL, 
	copay_percent NUMERIC(5, 2) NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	username VARCHAR(50) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	display_name VARCHAR(100) NOT NULL, 
	`role` VARCHAR(20) NOT NULL, 
	hospital_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_user_role CHECK (role in ('policyholder','hospital','claims_officer','admin')), 
	UNIQUE (username), 
	FOREIGN KEY(hospital_id) REFERENCES hospitals (id)
);

CREATE TABLE policies (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	holder_user_id INTEGER NOT NULL, 
	plan_id INTEGER NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(holder_user_id) REFERENCES users (id), 
	FOREIGN KEY(plan_id) REFERENCES plans (id)
);

CREATE TABLE members (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	policy_id INTEGER NOT NULL, 
	display_name VARCHAR(100) NOT NULL, 
	relationship VARCHAR(30) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(policy_id) REFERENCES policies (id)
);

CREATE TABLE claims (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	policy_id INTEGER NOT NULL, 
	member_id INTEGER NOT NULL, 
	hospital_id INTEGER NOT NULL, 
	claim_type VARCHAR(20) NOT NULL, 
	treatment_type VARCHAR(20) NOT NULL, 
	admission_date DATE NOT NULL, 
	discharge_date DATE NOT NULL, 
	requested_amount NUMERIC(12, 2) NOT NULL, 
	eligible_amount NUMERIC(12, 2), 
	description VARCHAR(255) NOT NULL, 
	decision_reason VARCHAR(500), 
	status VARCHAR(20) NOT NULL, 
	officer_user_id INTEGER, 
	created_by_user_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_claim_amount CHECK (requested_amount > 0), 
	CONSTRAINT ck_claim_status CHECK (status in ('draft','submitted','in_review','more_info','approved','rejected','paid')), 
	FOREIGN KEY(policy_id) REFERENCES policies (id), 
	FOREIGN KEY(member_id) REFERENCES members (id), 
	FOREIGN KEY(hospital_id) REFERENCES hospitals (id), 
	FOREIGN KEY(officer_user_id) REFERENCES users (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id)
);

CREATE INDEX ix_claims_officer_status ON claims (officer_user_id, status);

CREATE INDEX ix_claims_policy_status ON claims (policy_id, status);

CREATE TABLE claim_documents (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	claim_id INTEGER NOT NULL, 
	document_type VARCHAR(30) NOT NULL, 
	checklist_status VARCHAR(20) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (claim_id, document_type), 
	FOREIGN KEY(claim_id) REFERENCES claims (id)
);

CREATE TABLE claim_history (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	claim_id INTEGER NOT NULL, 
	sequence_no INTEGER NOT NULL, 
	from_status VARCHAR(20), 
	to_status VARCHAR(20) NOT NULL, 
	actor_user_id INTEGER NOT NULL, 
	note VARCHAR(500) NOT NULL, 
	timestamp DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (claim_id, sequence_no), 
	FOREIGN KEY(claim_id) REFERENCES claims (id), 
	FOREIGN KEY(actor_user_id) REFERENCES users (id)
);

CREATE INDEX ix_history_claim_time ON claim_history (claim_id, timestamp);

CREATE TABLE settlements (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	claim_id INTEGER NOT NULL, 
	payee_type VARCHAR(20) NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	recorded_by_user_id INTEGER NOT NULL, 
	recorded_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (claim_id), 
	FOREIGN KEY(claim_id) REFERENCES claims (id), 
	FOREIGN KEY(recorded_by_user_id) REFERENCES users (id)
);
