-- Criar tabela de carregadores
CREATE TABLE IF NOT EXISTS charging_stations (
    id VARCHAR(10) PRIMARY KEY,
    location VARCHAR(100) NOT NULL,
    address VARCHAR(200) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    power INTEGER NOT NULL,
    available BOOLEAN NOT NULL DEFAULT true
);

-- Inserir dados dos carregadores
INSERT INTO charging_stations (id, location, address, price, power, available) VALUES
('1', 'Matosinhos', 'Rua do Mar 123', 0.35, 50, true),
('2', 'Matosinhos', 'Avenida da Praia 456', 0.40, 150, true);