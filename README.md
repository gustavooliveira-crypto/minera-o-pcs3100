# Distribuição das Contribuições em Projetos de Ingressantes — Mineração de Repositórios Git

Pacote de artefatos do artigo *"Distribuição das Contribuições em Projetos de
Ingressantes de Engenharia de Computação: uma Análise de Repositórios Git"*
(CTIC-ES, CBSoft 2026), referente à disciplina PCS3100 — Introdução à
Engenharia da Computação (EPUSP/USP).

Os scripts mineram os repositórios Git dos grupos de projeto e produzem
métricas de distribuição das contribuições registradas (número de *commits*,
índice de Gini, e separação entre código e documentação por autor).

## Conteúdo

| Arquivo | Descrição |
|---|---|
| `clone_all.py` | Clona vários repositórios a partir de um `repos.txt` e gera um manifesto (pasta → grupo). |
| `mine_repos.py` | Minera os repositórios clonados e gera as métricas por autor e por grupo (dados anonimizados). |
| `colaboracao_grupos.csv` | Resultado anonimizado por grupo: autores no Git, total de *commits*, % do maior contribuidor e índice de Gini. |

## Como executar

Requisitos: Python 3.9+ e Git instalados.

```bash
# 1. Clonar os repositórios listados em repos.txt
python clone_all.py repos.txt --dest ./repos

# 2. Minerar e gerar as métricas
python mine_repos.py ./repos --out ./resultados
```

### Formato do `repos.txt`

Uma entrada por linha (não incluída neste repositório, por conter dados
que identificam os grupos):

```
https://github.com/usuario/projeto --> grupo 1
https://github.com/usuario/outro   --> grupo 1
```

Repositórios com o mesmo rótulo de grupo são somados na análise.

## Métricas

- **% do maior contribuidor**: parcela de *commits* do autor mais ativo do grupo.
- **Índice de Gini**: desigualdade global da distribuição de *commits* entre os
  autores (0 = distribuição igual; valores maiores = mais concentração).
- **Código vs. documentação**: linhas de código e de documentação (*markdown*)
  por autor, considerando apenas a documentação versionada.

## Anonimização e privacidade

Os autores são anonimizados (Autor 1, Autor 2, …) por grupo. O script gera um
arquivo `_chave_privada.csv` com a correspondência para nomes/e-mails reais —
**este arquivo nunca deve ser publicado** e está listado no `.gitignore`, assim
como o `repos.txt` e a pasta `repos/`. Apenas dados agregados e anonimizados
são disponibilizados neste repositório.

## Limitações

As métricas refletem as *contribuições registradas no Git*, e não a totalidade
da colaboração: trabalho feito em programação em par, reuniões, montagem de
hardware ou documentos externos ao repositório pode não estar representado.
