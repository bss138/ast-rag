# 데이터 규약

파이프라인 단계 간 주고받는 파일 형식. 여기 적힌 필드명을 각 단계가 지킨다.

## 파일 흐름

```
corpus/<repo>/*.c,*.h
  → [parse.py]     → data/<corpus>/nodes.jsonl, parse_stats.json
  → [chunk.py]     → data/<corpus>/chunks.jsonl
  → [callgraph.py] → data/<corpus>/call_graph.json
  → [index.py]     → indexes/<corpus>_<chunking>_<embedding>/
  → [retrieve.py]  → (메모리)
  → [evaluate.py]  → eval/results/config_<X>.json
```

`<corpus>`는 `tiny_network` 또는 `libevent`.

## nodes.jsonl — parse.py 출력

한 줄에 노드 하나.

```json
{
  "node_id": "network.c::function_definition::49",
  "file": "network.c",
  "node_type": "function_definition",
  "symbol": "mem_alloc",
  "start_row": 49,
  "end_row": 53,
  "start_byte": 1120,
  "end_byte": 1226,
  "is_static": true,
  "fallback": false
}
```

- `node_id` = `파일::타입::시작줄`. static 함수 이름 충돌(do_read, mem_alloc 등)을 줄 번호로 해소
- `symbol`이 null일 수 있음 (익명 enum 등)
- `start_row`는 1부터. tree-sitter의 start_point[0] + 1
- 바이트 오프셋은 저장은 하되 비교·테스트에 쓰지 않는다 (CRLF/LF에 따라 달라짐)

## parse_stats.json — parse.py 출력

```json
{
  "network.c": {
    "lines": 837,
    "total_nodes": 7288,
    "error_nodes": 23,
    "error_ratio": 0.00316,
    "function_definition": 43,
    "struct_definitions": 0,
    "prototypes": 5,
    "fallback": false
  }
}
```

`struct_definitions`는 body 필드가 있는 struct_specifier만 센다.
body 없는 것은 타입 참조이므로 제외 (network.c에 66개 존재).

## chunks.jsonl — chunk.py 출력

```json
{
  "chunk_id": "network.c::mem_alloc::49",
  "file": "network.c",
  "symbol": "mem_alloc",
  "node_type": "function_definition",
  "start_row": 49,
  "end_row": 53,
  "signature": "static void* mem_alloc( size_t cap )",
  "doc_comment": "",
  "module": "memory helpers",
  "body": "static void* mem_alloc( size_t cap ) {\n    void* ret = malloc(cap);\n...",
  "embed_text": "// File: network.c\n// Symbol: mem_alloc (function_definition)\n// Signature: ...\n\n<body>",
  "token_len": 41,
  "fallback": false
}
```

- `body` = LLM 컨텍스트에 넣을 원본
- `embed_text` = 헤더 붙인 검색용. Phase 8에서 헤더 유무 실험을 하려면 둘 다 필요
- 두 필드 모두 `\r\n` → `\n` 정규화 후 저장 (tiny-network 원본이 CRLF)
- `module`은 파일 내 섹션 주석에서 추출 (network.c의 `// connection`, `// server` 등)

## call_graph.json — callgraph.py 출력

```json
{
  "edges": [["net_server_create", "str_to_sockaddr"]],
  "index": {
    "net_server_create": {
      "chunk_id": "network.c::net_server_create::287",
      "callees": ["str_to_sockaddr", "nb_socket"],
      "callers": []
    }
  },
  "stats": {
    "direct": 165,
    "indirect": 3,
    "coverage": 0.982,
    "internal_edges": 55
  }
}
```

- `direct` = call_expression의 function 필드가 identifier인 경우
- `indirect` = field_expression 등 (함수 포인터 호출). 엣지로 만들지 않고 카운트만
- 내부 엣지는 심볼 테이블에 있는 이름만. 매크로와 libc는 자동 배제됨

## eval_set.jsonl — 손으로 작성

```json
{
  "qid": "q01",
  "type": "concept",
  "question": "이벤트 루프가 한 바퀴 도는 동안 무슨 일이 일어나?",
  "gold": [{"file": "event.c", "symbol": "event_base_loop"}],
  "gold_mode": "any",
  "note": "판정 근거 메모"
}
```

- `type`: concept | identifier | struct | multi
- `gold_mode`: `any`(하나라도 맞으면 성공) | `coverage`(회수 비율)
- `gold`에 줄 번호를 적지 않는다. 실행 시 nodes.jsonl에서 조회.
  코퍼스 커밋을 바꿔도 질문셋이 안 깨지게 하기 위함
- 질문에 함수명을 넣지 않는다 (identifier 유형만 예외)

## config_X.json — evaluate.py 출력

```json
{
  "config": "D",
  "chunking": "ast",
  "embedding": "jina-code",
  "retrieval": "hybrid",
  "corpus_commit": "abc123",
  "per_question": [
    {"qid": "q01", "recall@5": 1.0, "rr": 0.5, "returned": ["..."]}
  ],
  "aggregate": {"recall@5": 0.71, "mrr": 0.58},
  "by_type": {"concept": 0.65, "identifier": 0.88, "struct": 0.70, "multi": 0.55}
}
```

`per_question`을 반드시 남긴다. 집계만 저장하면 실패 케이스 분석 때 전부 재실행해야 함.

## CLI 규약

```
python -m src.parse     --corpus {tiny_network|libevent}
python -m src.chunk     --corpus ...
python -m src.callgraph --corpus ...
python -m src.index     --corpus libevent --embedding {minilm|jina} --chunking {ast|fixed}
python -m src.evaluate  --corpus libevent --config {A|B|C|D|E}
```

항상 프로젝트 루트에서 실행. src/ 안에서 실행하면 ModuleNotFoundError.