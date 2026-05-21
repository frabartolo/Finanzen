-- Datenbank-Schema für Finanzverwaltung (MariaDB/MySQL)

CREATE TABLE IF NOT EXISTS accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,
    bank VARCHAR(255),
    iban VARCHAR(34),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    type ENUM('income', 'expense') NOT NULL,
    parent_id INT,
    FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_path VARCHAR(512) NULL COMMENT 'Relativ zum Projekt-Root, z.B. data/processed/…/konto.pdf',
    file_name VARCHAR(255) NULL,
    file_sha256 CHAR(64) NULL COMMENT 'SHA-256 der PDF-Datei',
    account_id INT NULL,
    raw_text MEDIUMTEXT,
    amount DECIMAL(15,2) NULL,
    category VARCHAR(255) NULL,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE SET NULL,
    UNIQUE KEY uq_documents_source_path (source_path),
    INDEX idx_documents_account (account_id),
    INDEX idx_documents_sha256 (file_sha256),
    INDEX idx_documents_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    date DATE NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    description TEXT,
    category_id INT,
    source VARCHAR(50), -- 'fints', 'pdf', 'postbank_csv', …
    transaction_hash VARCHAR(64) NULL COMMENT 'SHA-256 hex, idempotenter Import',
    document_id INT NULL COMMENT 'Quell-PDF (documents), wenn aus PDF-Import',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL,
    INDEX idx_transactions_date (date),
    INDEX idx_transactions_account (account_id),
    INDEX idx_transactions_category (category_id),
    INDEX idx_transactions_document (document_id),
    UNIQUE KEY uq_transactions_account_hash (account_id, transaction_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;