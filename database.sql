-- Finora Budget - estrutura do banco (MySQL/MariaDB do XAMPP)
-- Importe este arquivo pelo phpMyAdmin (aba "Importar").
CREATE DATABASE IF NOT EXISTS finora_budget
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE finora_budget;

CREATE TABLE IF NOT EXISTS movimentacoes (
  id        INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  descricao VARCHAR(120)  NOT NULL,
  valor     DECIMAL(12,2) NOT NULL,
  tipo      ENUM('receita','despesa') NOT NULL,
  categoria VARCHAR(40)   NOT NULL,
  `data`    DATE          NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT chk_mov_valor CHECK (valor > 0),
  INDEX idx_mov_data (`data`),
  INDEX idx_mov_tipo (tipo)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS metas (
  id             INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  nome           VARCHAR(100)  NOT NULL,
  valor_objetivo DECIMAL(12,2) NOT NULL,
  valor_acumulado DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  PRIMARY KEY (id),
  CONSTRAINT chk_meta_objetivo CHECK (valor_objetivo > 0),
  CONSTRAINT chk_meta_acumulado CHECK (valor_acumulado >= 0)
) ENGINE=InnoDB;
