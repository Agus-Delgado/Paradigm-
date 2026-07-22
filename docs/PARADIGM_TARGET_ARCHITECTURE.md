# Paradigm — Arquitectura objetivo

**Fecha:** 2026-07-22  
**Entrada de referencia:** [`PARADIGM_CURRENT_STATE.md`](PARADIGM_CURRENT_STATE.md) y la documentación principal del repo.  
**Alcance:** definir una arquitectura objetivo breve, clara y no operativa.

## 1. Propósito

Paradigm es una plataforma personal y experimental de inteligencia aplicada. No es hoy un producto comercial ni multiusuario. El objetivo es ordenar análisis, lenguaje, automatización controlada y aprendizaje en un marco auditable.

Se distinguen tres planos: arquitectura actual, arquitectura objetivo y legacy.

## 2. Alcance actual

Hoy la base sigue siendo local: Streamlit como UI, Python como runtime, SQLite como persistencia analítica y archivos como soporte de artefactos. La experiencia actual expone ocho páginas: Executive Overview, Conciliación, No-Show ML, Forecasting, AI Conversational Insights, Governance & Improvement, Automation Lab y Paradigm Copilot.

Como primera fase ya implementada:

- Copilot V1 funcional para explicar/revisar SQL y Python, analizar errores y proponer correcciones (sin ejecutar código, sin editar archivos, con revisión humana obligatoria).
- Automation Lab estructural (sin ejecución operativa).
- Governance & Improvement estructural (sin seguimiento operativo persistente).

Eso describe un laboratorio individual, reproducible y sin dependencia obligatoria de una base remota.

## 3. Módulos objetivo

- **Paradigm**: núcleo de orquestación de la plataforma.
- **ClarusFlow**: ingesta, calidad, transformación y gobierno de datos.
- **LumenVox**: lenguaje, feedback, clasificación y análisis textual.
- **Paradigm Copilot**: compañero contextual para SQL, Python y Data Science.
- **Automation Lab**: automatizaciones, disparadores, acciones, aprobaciones e historial.
- **Governance & Improvement**: riesgos, limitaciones, evaluaciones, decisiones y mejoras.

Paradigm coordina; ClarusFlow prepara datos; LumenVox interpreta texto. Copilot asiste; Automation Lab ejecuta flujos controlados; Governance & Improvement registra y mejora.

## 4. Relación entre Paradigm, ClarusFlow y LumenVox

La relación objetivo es modular, no rígida. ClarusFlow aporta evidencia confiable, LumenVox aporta capacidad lingüística y Paradigm consume ambas para análisis, copiloto, automatización y gobernanza.

No se describe una integración comercial entre productos, sino una colaboración conceptual dentro de una plataforma personal.

## 5. Persistencia

La persistencia actual seguirá siendo local mediante SQLite y archivos. Ahí viven el mart, reportes, experimentos, exportaciones y materiales de apoyo a la UI. PostgreSQL o una base remota quedan como posibilidad futura, no como requisito actual.

## 6. Principios del Copilot

- Contexto primero: operar sobre el entorno actual.
- Trazabilidad: citar archivos, consultas o artefactos.
- Asistencia, no autoridad: sugerir y explicar, no ocultar decisiones.
- Lectura segura: priorizar consultas y análisis de solo lectura.
- Foco disciplinar: SQL, Python y Data Science.
- Incertidumbre explícita: si falta evidencia, decirlo.

## 7. Límites actuales

- No hay un producto comercial listo para multiusuario.
- No existe una persistencia remota obligatoria.
- No hay automatización operativa completa ni ejecución autónoma real.
- Copilot no ejecuta SQL/Python ni mantiene historial persistente.
- No debe asumirse causalidad donde hoy solo hay análisis, ranking o simulación.
- La IA generativa y la automatización siguen siendo asistidas y locales.

## 8. Evolución por fases

### Fase 1: ordenar la base
Consolidar ClarusFlow como frente de datos, Paradigm como orquestador y LumenVox como capa lingüística. Mantener SQLite y archivos como persistencia principal. Esta fase ya incluye la base modular inicial visible: Copilot V1 y páginas estructurales de Automation Lab y Governance & Improvement.

### Fase 2: separar capacidades
Desacoplar mejor Copilot, Automation Lab y Governance & Improvement para que cada uno tenga responsabilidades claras y contratos internos estables.

### Fase 3: reforzar control y aprendizaje
Formalizar aprobaciones, historial, evaluaciones y decisiones dentro de Governance & Improvement y Automation Lab. Incorporar capacidades avanzadas de Copilot (sin perder revisión humana).

### Fase 4: evaluar persistencia futura
Solo si hace falta por volumen, colaboración o despliegue, considerar PostgreSQL o una base remota, junto con colaboración multiusuario.

## 9. Componentes legacy

Son legacy los componentes que aún existen pero no deberían definir la arquitectura objetivo: la entrada Streamlit histórica como producto único, los puentes de compatibilidad con código anterior y cualquier módulo que mezcle UI, lógica y persistencia sin separación clara.

Si un componente ya cumple una función clara dentro de Paradigm, ClarusFlow, LumenVox, Copilot, Automation Lab o Governance & Improvement, se conserva y se reubica mentalmente allí; si no, permanece como legacy hasta su migración o retiro.
