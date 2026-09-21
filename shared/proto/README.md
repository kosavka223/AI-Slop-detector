gRPC Contracts
analyzer.proto
Интерфейс между ML-моделями (NVIDIA Triton) и сервисами-анализаторами.

Правила изменений
Любое изменение .proto — только через PR с ревью Team Lead.
После изменения proto — поднять schema_version в shared/models/kafka.py.
Обратная совместимость: новые поля — только с новым номером, удаление полей запрещено.
Генерация Python-клиента (когда понадобится)
pip install grpcio-toolspython -m grpc_tools.protoc -I shared/proto \    --python_out=shared/proto/gen \    --grpc_python_out=shared/proto/gen \    shared/proto/analyzer.proto
Пока генерировать не нужно — файлы нужны для фиксации контракта.
