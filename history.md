

## 2026-09-30 14:03 (urn:li:share:7511108436823240704)
NOT IN com NULL pode zerar o resultado da sua query sem dar nenhum erro.

Se a subquery trouxer um único NULL, a condição nunca é verdadeira:

SELECT * FROM clientes
WHERE id NOT IN (SELECT cliente_id FROM pedidos);

Se algum cliente_id for NULL, a query não retorna nada.

Prefira NOT EXISTS:

SELECT * FROM clientes c
WHERE NOT EXISTS (
  SELECT 1 FROM pedidos p WHERE p.cliente_id = c.id
);

#SQL #EngenhariaDeDados
