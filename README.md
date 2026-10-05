# Langfuse local service

Dịch vụ Langfuse độc lập để các hệ thống agentic gửi tracing về một nơi.
Giai đoạn hiện tại: thử nghiệm nội bộ trên Windows + Docker Desktop (Linux containers).
Langfuse Web/API và Worker được ghim cùng phiên bản `4.50.0`; Python SDK `4.16.0`.

## Khởi động

Docker Desktop phải bật Linux containers và Docker Compose v2. Tài liệu Langfuse
đề xuất VM 4 cores, 16 GiB RAM và khoảng 100 GiB storage làm mốc tham khảo;
trên Docker Desktop cần cấp đủ tài nguyên cho toàn bộ stack và theo dõi thực tế.

Từ PowerShell tại thư mục dự án:

```powershell
python scripts/init_env.py
.\scripts\stack.ps1 -Action validate
.\scripts\stack.ps1 -Action start
python scripts/health.py
```

Nếu PowerShell chặn chạy script, dùng trực tiếp CLI, không cần đổi execution policy:

```powershell
docker compose config --quiet
docker compose up -d --wait --wait-timeout 600
docker compose ps -a
```

Nếu Docker không được tìm thấy trong shell, wrapper tự tìm các vị trí phổ biến.
Cũng có thể chỉ rõ đường dẫn:

```powershell
.\scripts\stack.ps1 -Action start -DockerPath "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe"
```

Nếu shell bị hạn chế quyền đọc/chạy Docker CLI, chạy các lệnh này trong terminal
Windows của bạn có quyền truy cập Docker Desktop. Không cài lại Docker chỉ vì CLI
không truy cập được từ một phiên shell cụ thể.

Mở <http://localhost:3000>, Sign up để tạo tài khoản đầu tiên, sau đó tạo organization,
project và API keys trong Project Settings. Không có tài khoản admin mặc định.
Lưu API keys vào `examples/python/.env`, không vào cấu hình server.

| Thành phần | Địa chỉ trên máy Windows |
| --- | --- |
| Web/UI/API | http://localhost:3000 |
| Worker health | http://localhost:3030/api/health |
| MinIO S3/media | http://localhost:9090 |
| MinIO console | http://localhost:9091 |
| PostgreSQL, ClickHouse, Redis | Chỉ trong mạng Docker Compose |

`init_env.py` tạo secrets ngẫu nhiên, không ghi đè `.env` hiện có và không in secrets.
Không dùng trực tiếp giá trị `__GENERATE__` trong `.env.example`.
Sau khi tạo tài khoản cần hạn chế người có quyền sử dụng máy; cấu hình này dành cho thử nghiệm.

## Gửi trace mẫu

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r examples/python/requirements.txt
Copy-Item examples/python/.env.example examples/python/.env
# Điền LANGFUSE_PUBLIC_KEY và LANGFUSE_SECRET_KEY trong examples/python/.env.
.\.venv\Scripts\python.exe examples/python/smoke_trace.py --check-auth --session-id demo-first-run
.\.venv\Scripts\python.exe examples/python/smoke_trace.py --check-auth --simulate-tool-error
```

Mẫu không gọi LLM thật. Model, token usage và chi phí bằng 0 đều là dữ liệu mô phỏng;
model thật cần gửi usage và cấu hình pricing phù hợp nếu muốn theo dõi chi phí.
Trong UI kiểm tra trace `demo-agent.run`, các observation `plan`, `deployment-status`,
`summarize`, session ID, latency, usage và trạng thái ERROR khi mô phỏng tool lỗi.
`email` và `api_key` trong input/output phải thành `[REDACTED]`.
`--check-auth` kiểm tra kết nối và project keys, chưa chứng minh trace đã được lưu;
cần xác nhận trên UI sau khi Worker xử lý.

Thử logic khi chưa có SDK hoặc service:

```powershell
python examples/python/smoke_trace.py --offline
```

## Tích hợp hệ thống agentic

- Dùng SDK/integration Langfuse trong từng hệ thống; chưa cần proxy hoặc gateway riêng.
- Một trace cho mỗi lượt chạy, observation con cho từng bước, tool và LLM.
- Dùng tên ổn định như `research-agent.run`, `search-documents`, `answer-generation`;
  không đưa prompt, user ID hay secrets vào tên observation.
- Gắn `system`, environment, session ID; session gom nhiều lượt trong cùng cuộc hội thoại.
  Có thể tách project/API keys theo hệ thống hoặc dev/staging để kiểm soát dữ liệu.
- Dùng OpenTelemetry context propagation: inject `traceparent`/`tracestate` vào HTTP
  headers/message metadata ở bên gửi và extract trước khi tạo span ở bên nhận.
  Chỉ dùng session ID không tạo được quan hệ cha-con qua nhiều dịch vụ.
- Gửi tracing bất đồng bộ theo batch; mẫu dùng batch 32, chu kỳ 2 giây và timeout exporter
  5 giây. Flush/shutdown khi kết thúc ứng dụng, không gọi `auth_check` ở mỗi request.
- `telemetry.py` giữ nguyên lỗi của business logic và bỏ qua lỗi instrumentation.
  Exporter có thể retry và mất dữ liệu khi hết retry, ứng dụng chết hoặc queue đầy;
  đây chưa phải pipeline bảo đảm không mất trace.
- Chỉ gửi các trường đã cho phép. Redaction mẫu xử lý một số khóa credentials/PII,
  email, `sk-...`, Bearer token; không phát hiện được mọi secret hoặc PII trong văn bản.
  Mask của SDK không tự bảo vệ dữ liệu từ mọi instrumentation OpenTelemetry bên thứ ba.

| Agent chạy ở đâu | LANGFUSE_BASE_URL |
| --- | --- |
| Trực tiếp trên Windows | `http://localhost:3000` |
| Container cùng mạng Compose | `http://langfuse-web:3000` |
| Container Docker Desktop khác mạng | `http://host.docker.internal:3000` nếu kiểm tra truy cập thành công |

Đối với agent trong container, phương án ổn định là gắn container vào mạng
`langfuse-local_default` và dùng `http://langfuse-web:3000`. Cổng host đang bind
`127.0.0.1`; khả năng truy cập qua `host.docker.internal` tùy Docker Desktop và cần kiểm tra.
Ví dụ cấu hình trong Compose của agent:

```yaml
services:
  agent:
    # image/build và API keys do hệ thống agent của bạn cung cấp.
    environment:
      LANGFUSE_BASE_URL: http://langfuse-web:3000
    networks: [langfuse]
networks:
  langfuse:
    external: true
    name: langfuse-local_default
```

Media/multimodal cần endpoint S3 mà bên upload và browser truy cập được;
ví dụ hiện tại chỉ gửi text. Chưa mở LAN. Khi mở LAN cần điều chỉnh bind, URLs,
firewall, HTTPS và chính sách tài khoản trước khi đưa dữ liệu thật vào.

## Vận hành và kiểm chứng

```powershell
.\scripts\stack.ps1 -Action status
.\scripts\stack.ps1 -Action logs
docker compose logs --tail 100 clickhouse minio redis postgres
docker system df -v
docker stats --no-stream
.\scripts\stack.ps1 -Action stop
.\scripts\stack.ps1 -Action start
```

Kiểm chứng dữ liệu bền vững: gửi trace với session ID cố định, xác nhận trên UI,
chạy stop/start, rồi tìm lại cùng trace và tài khoản. Stop dùng `compose down`
và giữ nguyên named volumes. Không thay project name nếu muốn dùng lại dữ liệu.

Kiểm chứng khi Langfuse ngừng: sau khi đã cấu hình keys và gửi thành công trace mẫu,
chạy `docker compose stop langfuse-web langfuse-worker`, rồi chạy mẫu **không có**
`--check-auth`. Kết quả agent vẫn phải in ra và exit 0; exporter có thể báo lỗi,
trace có thể mất. Khôi phục bằng `docker compose up -d --wait --wait-timeout 600`.
Không dùng `--offline` cho phép thử này vì cần kiểm tra lỗi gửi thật.

Logs stdout/stderr của mỗi container giới hạn 3 file x 10 MiB. ClickHouse file logger
giới hạn 3 x 10 MiB và mức warning. Các giới hạn này không giới hạn trace storage,
ClickHouse system log tables hoặc MinIO events; theo dõi disk Docker Desktop thường xuyên.
Giai đoạn thử nghiệm chưa bật retention tự động; reset thử nghiệm thủ công khi cần.

### Nâng cấp và reset

Giữ bản sao `.env`, nhất là SALT/ENCRYPTION_KEY. Đổi mật khẩu `.env` không tự cập nhật
credentials trong PostgreSQL/ClickHouse đã khởi tạo. Không tạo lại secrets để sửa lỗi kết nối.

Langfuse Web/Worker được ghim patch release. Infrastructure giữ baseline upstream:
PostgreSQL 17, ClickHouse 25.12, Redis 7 và MinIO Chainguard rolling tag.
Sau lần pull thành công, có thể lấy RepoDigest của từng infrastructure image và
điền `POSTGRES_IMAGE`, `CLICKHOUSE_IMAGE`, `REDIS_IMAGE`, `MINIO_IMAGE` trong `.env`
thành `repository@sha256:...` để khóa chính xác. Không lấy digest từ container ID.

```powershell
docker image inspect cgr.dev/chainguard/minio:latest --format '{{json .RepoDigests}}'
```

Trước nâng cấp: đọc release notes/migration guide, sao lưu nhất quán các database,
object storage và secrets khi đã có dữ liệu cần giữ. Chưa có backup tự động trong repo này.
Đổi `LANGFUSE_VERSION` cho cả Web và Worker rồi:

```powershell
docker compose pull
docker compose up -d --wait --wait-timeout 600
python scripts/health.py
```

Kiểm tra lại trace mẫu. Migration có thể khiến quay về image cũ không tương thích;
phục hồi dữ liệu từ backup nếu cần rollback.

**Chỉ khi chủ động muốn xóa toàn bộ dữ liệu thử nghiệm của stack này**:

```powershell
docker compose down --volumes
```

Lệnh trên xóa tài khoản, projects, traces và object storage; giữ `.env`.
Không dùng Docker prune cho việc reset stack.

## Kiểm tra mã và tình trạng xác minh

```powershell
python -m unittest discover -s tests -v
```

Các unit tests kiểm tra redaction, bảo toàn lỗi nghiệp vụ và fail-open khi setup/update/
cleanup telemetry lỗi; chạy được không cần SDK hay Docker. Không thay thế kiểm chứng
thực tế về tương thích image, migrations, ingestion và persistent volumes.
Xem `VALIDATION.md` để biết những bước đã chạy trong phiên triển khai này.

## Tài liệu chính thức

- [Kiến trúc self-host](https://langfuse.com/self-hosting)
- [Docker Compose và sizing](https://langfuse.com/self-hosting/deployment/docker-compose)
- [Compose upstream tại release 4.50.0](https://github.com/langfuse/langfuse/blob/v4.50.0/docker-compose.yml)
- [Health endpoints](https://langfuse.com/self-hosting/configuration/health-readiness-endpoints)
- [Python SDK reference](https://python.reference.langfuse.com/langfuse)
- [Releases](https://github.com/langfuse/langfuse/releases)

#   l a n g f u s e _ s e r v i c e  
 