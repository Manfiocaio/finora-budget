-- Finora Budget - estrutura do banco (MySQL/MariaDB do XAMPP)
-- Importe este arquivo pelo phpMyAdmin (aba "Importar").
CREATE DATABASE IF NOT EXISTS finora_budget
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE finora_budget;

CREATE TABLE IF NOT EXISTS usuarios (
  id        INT UNSIGNED NOT NULL AUTO_INCREMENT,
  email     VARCHAR(254) NOT NULL,
  senha_hash VARCHAR(255) NOT NULL,
  nome      VARCHAR(80) NULL,
  foto_perfil VARCHAR(100) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_usuarios_email (email)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS movimentacoes (
  id        INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  descricao VARCHAR(120)  NOT NULL,
  valor     DECIMAL(12,2) NOT NULL,
  tipo      ENUM('receita','despesa') NOT NULL,
  categoria VARCHAR(40)   NOT NULL,
  `data`    DATE          NOT NULL,
  user_id   INT UNSIGNED  NULL,
  PRIMARY KEY (id),
  CONSTRAINT chk_mov_valor CHECK (valor > 0),
  INDEX idx_mov_data (`data`),
  INDEX idx_mov_tipo (tipo),
  INDEX idx_mov_usuario_data (user_id, `data`),
  CONSTRAINT fk_movimentacoes_usuario FOREIGN KEY (user_id) REFERENCES usuarios(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS metas (
  id             INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  nome           VARCHAR(100)  NOT NULL,
  valor_objetivo DECIMAL(12,2) NOT NULL,
  valor_acumulado DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  acompanhar_saldo TINYINT(1) NOT NULL DEFAULT 0,
  user_id        INT UNSIGNED NULL,
  PRIMARY KEY (id),
  CONSTRAINT chk_meta_objetivo CHECK (valor_objetivo > 0),
  CONSTRAINT chk_meta_acumulado CHECK (valor_acumulado >= 0),
  INDEX idx_metas_usuario (user_id),
  CONSTRAINT fk_metas_usuario FOREIGN KEY (user_id) REFERENCES usuarios(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS investimentos (
  id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id        INT UNSIGNED NOT NULL,
  produto        VARCHAR(40) NOT NULL,
  instituicao    VARCHAR(100) NOT NULL,
  valor_inicial  DECIMAL(12,2) NOT NULL,
  saldo_atual    DECIMAL(12,2) NOT NULL,
  indexador      VARCHAR(20) NOT NULL,
  taxa_anual     DECIMAL(7,3) NULL,
  data_aplicacao DATE NOT NULL,
  vencimento     DATE NULL,
  PRIMARY KEY (id),
  CONSTRAINT chk_investimento_valor CHECK (valor_inicial > 0),
  CONSTRAINT chk_investimento_saldo CHECK (saldo_atual >= 0),
  INDEX idx_investimentos_usuario_data (user_id, data_aplicacao),
  CONSTRAINT fk_investimentos_usuario FOREIGN KEY (user_id) REFERENCES usuarios(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS resgates_investimentos (
  id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  investimento_id INT UNSIGNED NOT NULL,
  user_id         INT UNSIGNED NOT NULL,
  valor           DECIMAL(12,2) NOT NULL,
  data_resgate    DATE NOT NULL,
  PRIMARY KEY (id),
  INDEX idx_resgates_usuario_data (user_id, data_resgate),
  CONSTRAINT fk_resgates_investimento FOREIGN KEY (investimento_id) REFERENCES investimentos(id),
  CONSTRAINT fk_resgates_usuario FOREIGN KEY (user_id) REFERENCES usuarios(id)
) ENGINE=InnoDB;
