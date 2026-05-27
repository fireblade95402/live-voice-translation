# Architecture

Diagrams covering the runtime data flow, the per-utterance sequence, and
the Azure deployment topology.

## Runtime components

```mermaid
flowchart LR
    subgraph Client[Browser]
        Mic([🎤 Mic])
        WACapture[Web Audio capture<br/>ScriptProcessor 24 kHz]
        UI[Chat UI<br/>+ language dropdowns]
        WAPlay[Web Audio playback<br/>gapless cursor]
        Spk([🔊 Speaker])
        Mic --> WACapture
        WAPlay --> Spk
    end

    subgraph Server[FastAPI server]
        WS[/WebSocket /ws/]
        Mgr[InterpreterManager]
        Interp[LiveInterpreter]
        WS --> Mgr --> Interp
    end

    subgraph Azure[Azure Speech resource]
        TR[TranslationRecognizer<br/>v2 universal endpoint<br/>Continuous LID]
        SA[SpeechSynthesizer<br/>lang A voice]
        SB[SpeechSynthesizer<br/>lang B voice]
    end

    Cred[DefaultAzureCredential<br/>az login / Managed Identity]

    WACapture -->|JSON audio b64| WS
    UI <-->|start / stop / partial / final / language_pair / error| WS
    WS -->|audio b64| WAPlay

    Interp --> TR
    Interp --> SA
    Interp --> SB
    Cred -. aad#resId#token .-> Interp
```

## Per-utterance sequence

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant B as Browser
    participant S as Server (FastAPI)
    participant I as LiveInterpreter
    participant R as TranslationRecognizer
    participant Y as SpeechSynthesizer (target)

    U->>B: speak
    B->>S: { type: audio, data: <b64 PCM16> }
    S->>I: push_audio()
    I->>R: PushAudioInputStream.write()

    R-->>I: recognizing (partial + detected source)
    I-->>S: { type: partial, source, translation, ... }
    S-->>B: forward partial
    B-->>U: live caption updates

    R-->>I: recognized (final + detected source + translations)
    I-->>S: { type: final, source, translation, ... }
    S-->>B: forward final

    I->>Y: speak_text_async(translation)
    Y-->>I: PCM16 24 kHz buffer
    I-->>S: { type: audio, data: <b64 PCM16> }
    S-->>B: forward audio
    B-->>U: gapless playback in target voice
```

## Azure deployment topology

```mermaid
flowchart TB
    Dev[Developer / CI] -->|azd up| ACR[(Azure Container Registry)]
    Dev -->|azd up| CAE[Container Apps Environment]

    subgraph ResourceGroup[Resource Group<br/>created by azd]
        ACR
        LAW[(Log Analytics Workspace)]
        UAMI[User-Assigned<br/>Managed Identity]
        CAE --> CA[Container App<br/>live-voice-translation]
        CAE --> LAW
        CA -.uses.-> UAMI
        UAMI -- AcrPull --> ACR
    end

    SR[(Existing Azure Speech<br/>resource)]
    UAMI -- Cognitive Services<br/>Speech User --> SR

    User([🌐 User]) -->|HTTPS / WSS| CA
    CA -->|Speech SDK<br/>AAD token| SR
```

### Notes

- The Speech resource lives **outside** the resource group `azd` creates;
  the Bicep `role-assignment.bicep` module parses the subscription + RG
  from `AZURE_SPEECH_RESOURCE_ID` and grants the role at that scope.
- The Container App pulls the image from ACR via the managed identity
  (`AcrPull`) — no admin user / registry password is provisioned.
- All Speech traffic is AAD-authenticated; no Speech keys are stored.
