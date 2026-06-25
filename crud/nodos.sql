USE sensores_remotos;

CREATE TABLE IF NOT EXISTS nodos (
  id        INT AUTO_INCREMENT PRIMARY KEY,
  sensor_id VARCHAR(50)  NOT NULL UNIQUE,   -- mismo id que aparece en `mediciones`
  mac       VARCHAR(17),                    -- identificación física del nodo
  nombre    VARCHAR(80),                    -- alias legible
  topico    VARCHAR(120) NOT NULL           -- tópico de comandos que escucha el Pico
);

GRANT SELECT, INSERT, DELETE ON sensores_remotos.nodos TO 'crud'@'%';
FLUSH PRIVILEGES;

INSERT INTO nodos (sensor_id, mac, nombre, topico) VALUES
  ('sensor_1', 'AA:BB:CC:DD:EE:01', 'Termostato sala',   'iot/sensor_1/comandos'),
  ('sensor_2', 'AA:BB:CC:DD:EE:02', 'Termostato cocina', 'iot/sensor_2/comandos'),
  ('sensor_3', 'AA:BB:CC:DD:EE:03', 'Termostato taller', 'iot/sensor_3/comandos');
