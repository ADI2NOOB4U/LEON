[1mdiff --git a/backend/app/core/providers/openai_compatible.py b/backend/app/core/providers/openai_compatible.py[m
[1mindex 083a017..3958e60 100644[m
[1m--- a/backend/app/core/providers/openai_compatible.py[m
[1m+++ b/backend/app/core/providers/openai_compatible.py[m
[36m@@ -1,4 +1,7 @@[m
[31m-﻿import httpx[m
[32m+[m[32m﻿from typing import Any[m
[32m+[m[32mfrom typing import Any[m
[32m+[m
[32m+[m[32mimport httpx[m
 [m
 from backend.app.config.settings import settings[m
 from backend.app.core.providers.base import ModelProvider[m
