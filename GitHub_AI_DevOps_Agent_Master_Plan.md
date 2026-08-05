# GitHub AI DevOps Agent - Master Plan

## Objetivo

Construir una plataforma SaaS multi-tenant basada en una GitHub App capaz de auditar, corregir, probar y desplegar proyectos automáticamente mediante agentes de IA.

## Principios

- API-first.
- Multi-tenant.
- Observabilidad total.
- Automatización por defecto.
- Todo cambio pasa por Pull Request.

## Arquitectura

```text
GitHub App
    │
Webhook
    │
Orchestrator
 ├─ Architecture Agent
 ├─ Security Agent
 ├─ Test Agent
 ├─ Refactor Agent
 ├─ Docs Agent
 ├─ Release Agent
 └─ Deploy Agent
    │
GitHub Actions
    │
GHCR
    │
Portainer/Kubernetes
```

# Roadmap

## Fase 0 - Fundación
- [ ] Crear repositorio
- [ ] Docker
- [ ] FastAPI
- [ ] PostgreSQL
- [ ] Redis
- [ ] Configuración .env
- [ ] Logging
- [ ] OpenTelemetry

## Fase 1 - GitHub App
- [ ] Crear GitHub App
- [ ] Configurar permisos
- [ ] Configurar Webhook
- [ ] Validar firma
- [ ] Instalar en organización

## Fase 2 - API
- [ ] Endpoint /webhook
- [ ] Endpoint /health
- [ ] Endpoint /metrics
- [ ] Endpoint /projects

## Fase 3 - Orquestador
- [ ] Cola de eventos
- [ ] Scheduler
- [ ] Gestión de estados
- [ ] Reintentos

## Fase 4 - Agentes
### Architecture Agent
- [ ] Detectar code smells
- [ ] Detectar duplicidad
- [ ] Recomendar arquitectura

### Security Agent
- [ ] Secret scanning
- [ ] Dependencias
- [ ] CVEs

### Test Agent
- [ ] Ejecutar tests
- [ ] Medir cobertura
- [ ] Generar pruebas

### Refactor Agent
- [ ] Aplicar diffs
- [ ] Reducir complejidad

### Docs Agent
- [ ] README
- [ ] ADR
- [ ] CHANGELOG

### Deploy Agent
- [ ] Docker
- [ ] GHCR
- [ ] Portainer
- [ ] Kubernetes

## Fase 5 - CI/CD
- [ ] Lint
- [ ] Unit Tests
- [ ] Build
- [ ] Publish GHCR
- [ ] Deploy

## Fase 6 - Multi-tenancy
- [ ] Organizaciones
- [ ] Repositorios
- [ ] Roles
- [ ] Secretos

## Fase 7 - Observabilidad
- [ ] Prometheus
- [ ] Grafana
- [ ] OpenTelemetry
- [ ] Auditoría

## Modelo de datos

- organizations
- users
- repositories
- installations
- audits
- pull_requests
- deployments
- metrics
- prompts
- jobs

## Estructura del repositorio

```text
github-ai-devops-agent/
 api/
 agents/
 services/
 workers/
 prompts/
 database/
 migrations/
 docker/
 .github/workflows/
 tests/
 docs/
```

## Prompts para Claude Code

Cada fase debe seguir este ciclo:

1. Analizar.
2. Diseñar.
3. Implementar.
4. Escribir pruebas.
5. Ejecutar pruebas.
6. Corregir.
7. Documentar.
8. Abrir Pull Request.

### Prompt maestro

```text
Actúa como arquitecto principal.

Nunca implementes una fase futura.

Para la fase actual:

- analiza el código existente
- propone el diseño
- implementa únicamente las tareas pendientes
- crea pruebas automatizadas
- verifica cobertura
- documenta cambios
- genera commits pequeños
- nunca rompas compatibilidad
- marca como completadas únicamente las tareas finalizadas
```

## Definition of Done

- Código compilando
- Tests verdes
- Cobertura >90%
- Sin secretos
- Docker funcional
- Documentación actualizada
- PR generado

## Roadmap SaaS

MVP
- Auditoría PR

V1
- Corrección automática

V2
- Deploy automático

V3
- Multiagente

V4
- Marketplace

V5
- SaaS comercial

## Métricas

- Tiempo de auditoría
- Tiempo de build
- Tiempo de deploy
- Coste IA
- Tokens
- PR aceptados
- Bugs detectados
- Vulnerabilidades
- Cobertura
- MTTR

