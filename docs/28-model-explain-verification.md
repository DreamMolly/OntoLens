# OntoLens 模型解释联调

`verify_model_explain.py` 验证工作台可选解释路由，不绑定 Nexent 模型，也不代替 Agent/run。

```powershell
.venv/Scripts/python.exe scripts/verify_model_explain.py
.venv/Scripts/python.exe scripts/verify_model_explain.py --live --output artifacts/model-explanation-verification.json
```

第一条只读本机配置，不发模型请求；第二条在明确配置端点、模型、凭证与获准范围后，对固定合成申请进行实际调用。`--output` 只允许项目内 JSON，排除 API key。

协议由 `ONTOLENS_MODEL_PROTOCOL` 选择 chat_completions、responses 或 messages。没有配置时明确 configured=false、live_request_sent=false；异常和空解释不能冒充成功，原决定与证据不变。

三种协议的离线契约、实际单次在线调用、持续稳定性与真实资料语义分别验收。Nexent 连接按平台收据与当前 observed_at 判断。
