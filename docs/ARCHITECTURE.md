# PDF QA Chatbot — Architecture Diagram

## High-level flow

```mermaid
flowchart TB
    subgraph UI["NiceGUI (thin UI)"]
        A[User: upload PDF / type message]
    end

    subgraph API["FastAPI"]
        B[POST /api/pdf/upload]
        C[POST /api/chat/stream]
        D[GET /api/session/:id]
    end

    subgraph App["App layer"]
        E[PDFParser.parse]
        F[AgentManager.add_pdf_to_knowledge]
        G[AgentManager.stream_response]
        H[AgentManager.get_session]
    end

    subgraph Storage["Storage"]
        I[(ChromaDB\nper session)]
        J[(SqliteDb\nchat history)]
    end

    subgraph External["External"]
        K[OpenAI\nembeddings + chat]
    end

    A --> B
    A --> C
    A --> D
    B --> E
    E --> F
    F --> I
    F --> K
    C --> G
    G --> I
    G --> J
    G --> K
    D --> H
    H --> J
```

## PDF upload flow

```mermaid
sequenceDiagram
    participant U as User
    participant UI as NiceGUI
    participant API as FastAPI
    participant P as PDFParser
    participant M as AgentManager
    participant C as ChromaDB
    participant O as OpenAI

    U->>UI: Select PDF
    UI->>API: POST /api/pdf/upload (file, session_id)
    API->>P: parse(filename, bytes)
    P->>P: validate_file (format, size, empty)
    P->>P: extract_text (pypdf)
    P-->>API: metadata, text
    API->>M: add_pdf_to_knowledge(session_id, text, filename)
    M->>M: get_knowledge(session_id) → ChromaDB collection
    M->>M: Write text to temp file
    M->>C: ainsert (Agno chunks + embed)
    C->>O: embed chunks
    O-->>C: vectors
    M-->>API: done
    API-->>UI: PDFUploadResponse(success, metadata, session_id)
    UI-->>U: Show "Document loaded"
```

## Chat / streaming flow (RAG)

```mermaid
sequenceDiagram
    participant U as User
    participant UI as NiceGUI
    participant API as FastAPI
    participant M as AgentManager
    participant A as Agno Agent
    participant C as ChromaDB
    participant S as SqliteDb
    participant O as OpenAI

    U->>UI: Send message
    UI->>M: stream_response(message, session_id)
    M->>M: get_agent(session_id) → Agent with Knowledge
    M->>A: arun(message, stream=True, session_id)
    A->>S: get_chat_history(session_id)
    S-->>A: previous messages
    A->>C: hybrid search (embed query, retrieve chunks)
    C-->>A: relevant PDF chunks
    A->>O: chat completion (context = history + chunks + message)
    loop Stream tokens
        O-->>A: token
        A-->>M: chunk
        M-->>UI: yield chunk
        UI-->>U: Update assistant bubble
    end
    M->>S: persist turn (user + assistant)
```

## Component diagram

```mermaid
flowchart LR
    subgraph Frontend
        UI[NiceGUI\n/ page]
    end

    subgraph Backend["FastAPI (main.py)"]
        R1[/api/chat/stream]
        R2[/api/pdf/upload]
        R3[/api/session/:id]
    end

    subgraph Core
        P[PDFParser\nvalidate → extract → metadata]
        AM[AgentManager\nsession + agent + knowledge]
    end

    subgraph Agno
        Agent[Agent\nOpenAIChat]
        KB[Knowledge\nChromaDB]
        DB[SqliteDb\nhistory]
    end

    subgraph Data
        Chroma[(ChromaDB\nvectors)]
        SQL[(agent.db)]
    end

    UI <--> R1
    UI <--> R2
    UI <--> R3
    R1 --> AM
    R2 --> P
    R2 --> AM
    R3 --> AM
    P --> AM
    AM --> Agent
    AM --> KB
    Agent --> KB
    Agent --> DB
    KB --> Chroma
    DB --> SQL
```

## Data flow (RAG at answer time)

```mermaid
flowchart LR
    Q[User message] --> E1[Embed query]
    E1 --> VS[ChromaDB\nhybrid search]
    VS --> Chunks[Relevant PDF chunks]
    H[Chat history\nSqliteDb] --> Ctx[Context]
    Chunks --> Ctx
    Q --> Ctx
    Ctx --> LLM[OpenAI\nchat]
    LLM --> Stream[Stream tokens]
    Stream --> UI[UI updates]
```
