# Алертинг (Prometheus + Alertmanager)

## Компоненты

| Файл | Назначение |
| --- | --- |
| `prometheus/alerts.yml` | Правила алертов |
| `scripts/run-alertmanager.sh` | Генерация конфига и запуск Alertmanager |
| `scripts/test-alert.sh` | Отправка тестового алерта |
| `.env.monitoring` | Секреты Telegram (`ALERTMANAGER_TELEGRAM_*`) |

## Настройка Telegram

1. Создайте бота через [@BotFather](https://t.me/BotFather), получите `BOT_TOKEN`.
2. Узнайте `CHAT_ID` (личный чат или группа): напишите боту, затем откройте `https://api.telegram.org/bot<TOKEN>/getUpdates`.
3. Добавьте в GitHub Secret `TEST_STAND_MONITORING_ENV_FILE`:

```env
ALERTMANAGER_TELEGRAM_BOT_TOKEN=123456:ABC...
ALERTMANAGER_TELEGRAM_CHAT_ID=-1001234567890
```

4. Задеплойте стенд или обновите `.env.monitoring` на VPS и перезапустите:

```bash
docker compose -f infra/monitoring/docker-compose.monitoring.yml \
  --env-file infra/monitoring/.env.monitoring up -d alertmanager prometheus
```

## Проверка

```bash
# Health
curl -fsS http://127.0.0.1:9093/-/healthy

# Тестовый алерт в Telegram
bash infra/monitoring/scripts/test-alert.sh

# Активные алерты в Prometheus
curl -s 'http://127.0.0.1:9090/api/v1/alerts' | python3 -m json.tool
```

## Правила

| Alert | Условие | Severity |
| --- | --- | --- |
| `AppScrapeDown` | `up==0` для app jobs, 2m | critical |
| `AppProbeDown` | blackbox probe failed, 2m | critical |
| `AppHealthDegraded` | `service_health_status==0`, 5m | warning |
| `HighErrorRate` | 4xx+5xx > 5%, 5m | warning |
| `HighLatencyP95` | p95 > 3s, 5m | warning |
| `HostHighMemory` | RAM > 90%, 5m | warning |
| `HostDiskLow` | disk free < 15%, 5m | critical |
| `HostHighCPU` | CPU > 90%, 10m | warning |

## Что делать при алерте

### AppScrapeDown / AppProbeDown
1. `docker ps` — контейнер запущен?
2. `docker logs <container> --tail 100`
3. Grafana → **Overview** → HTTP probes
4. Kibana → Discover → ошибки по `service`

### AppHealthDegraded
1. Часто: модель ещё грузится или нет артефактов `.pt`/`.csv`
2. `curl http://127.0.0.1:9000/health` (visual/text sidecars)
3. Проверить mount `/opt/visual-model-models`, `/opt/text-model-models`

### HighErrorRate / HighLatencyP95
1. Grafana → **Services** → RPS, error rate, p95 by handler
2. Kibana → saved search по 5xx / `duration_ms > 3000`
3. Повторить запрос вручную (`generate-monitoring-traffic.sh`)

### HostHighMemory / HostHighCPU
1. Grafana → **Infrastructure** → container memory/CPU
2. Частые виновники: `elasticsearch`, `visual-model-service`
3. При OOM: уменьшить `ES_JAVA_OPTS` или увеличить RAM VPS

### HostDiskLow
1. `df -h /`
2. `docker system df`
3. `docker image prune -af` (осторожно на стенде)

## Deploy maintenance

При деплое возможны кратковременные `AppProbeDown` — это нормально. Если алерты мешают, перед деплоем можно временно замьютить в Alertmanager UI (`/#/silences`).
