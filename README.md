# AI-Slop-detector

Enterprise-grade multi-signal analysis system for detecting AI-generated and AI-assisted email spam campaigns.



 Table of Contents

* Overview⁠￼
* Key Features⁠￼
    * Multi-Signal Analysis⁠￼
    * Campaign Detection⁠￼
    * Explainable AI⁠￼
    * False Positive Reduction⁠￼
* Architecture⁠￼
* Tech Stack⁠￼
* Quick Start⁠￼
* Documentation⁠￼
* Development⁠￼
* Project Structure⁠￼
* Testing⁠￼
* Performance Targets⁠￼
* Deployment⁠￼
* Roadmap⁠￼
* Contributing⁠￼
* License⁠￼
* Support⁠￼



 Overview

AI-Slop-detector is a multi-signal analysis system designed to detect AI-generated and AI-assisted email spam and phishing campaigns.

Instead of relying solely on traditional text classification, the system analyzes artifacts across the entire email creation pipeline:

* email text;
* HTML structure;
* embedded images;
* links and URLs;
* email metadata;
* campaign-level behavior and scaling patterns.

The goal is to identify combinations of signals that may indicate that an email was generated or significantly assisted by a Large Language Model (LLM), while reducing false positives from legitimate automated email systems such as CRM and SaaS platforms.

Research Foundation

The detection methodology is based on recent academic research:

* ⁠Do Spammers Dream of Electric Sheep? — IMC 2025
* ⁠Machine Learning and Watermarking for AI-Generated Phishing Detection
* ⁠SpearBot
* ⁠Phish-Master



 Key Features

Multi-Signal Analysis

The system combines several independent analyzers instead of relying on a single classifier.

 Text Analyzer

Analyzes the textual content of an email and detects:

* style inconsistencies;
* burstiness anomalies;
* LLM-specific writing patterns;
* unusual phrase structures;
* inconsistencies between different parts of the message.

 HTML Analyzer

Analyzes the structure and implementation of HTML emails.

It can detect:

* AI-generated HTML boilerplate;
* unusual DOM structures;
* unsupported CSS frameworks;
* Tailwind CSS classes used directly in email HTML;
* suspicious or unnecessarily complex layouts.

 Image Analyzer

Analyzes images embedded in emails.

The analyzer performs:

* OCR quality scoring;
* OCR/content consistency checks;
* GenAI artifact detection;
* image manipulation analysis;
* QR-code validation.

 Link Analyzer

Analyzes URLs and hyperlinks contained in emails.

It checks for:

* semantic mismatch between anchor text and destination URL;
* suspicious domains;
* domain reputation;
* LLM-generated DGA-like domains;
* inconsistencies between displayed and actual links.

Metadata Analyzer

Validates email authentication and metadata consistency.

It analyzes:

* email headers;
* DKIM;
* SPF;
* DMARC;
* domain alignment;
* inconsistencies between authentication results and message metadata.



 Campaign Detection

AI-assisted spam campaigns can generate thousands of slightly different messages.

To detect this behavior, the system provides campaign-level analysis:

* intent-based semantic clustering;
* semantic similarity instead of simple lexical comparison;
* automated detection of message variations;
* identification of LLM-generated paraphrasing;
* real-time campaign state tracking using Redis.

This allows the system to detect campaigns even when attackers generate many versions of essentially the same message.



 Explainable AI (XAI)

The system produces structured JSON results explaining why a message was classified as suspicious.

The output is designed for direct integration with SIEM/SOAR platforms.

Example

{
  "email_id": "msg_884291",
  "overall_risk": "High",
  "ai_assistance_score": 0.92,
  "classification": "AI-Assisted Spear-Phishing",
  "signals": {
    "text": {
      "score": 0.85,
      "reason": "Style clashing: formal LLM intro vs. aggressive slang CTA"
    },
    "html": {
      "score": 0.95,
      "reason": "Tailwind CSS classes in raw HTML (unsupported by standard email clients)"
    },
    "images": {
      "score": 0.70,
      "reason": "OCR mismatch on hero banner, GenAI upscaling artifacts detected"
    }
  },
  "campaign_context": {
    "cluster_id": "C-992A",
    "variations_detected": 45,
    "pattern": "LLM paraphrasing with low lexical overlap"
  }
}



 False Positive Reduction

The system is designed to distinguish malicious AI-assisted campaigns from legitimate automated email.

False-positive reduction includes:

* context-aware scoring;
* consideration of valid DKIM/SPF/DMARC alignment;
* differentiation between legitimate CRM/SaaS automation and malicious spam;
* whitelisting of known legitimate notification platforms;
* combination of multiple independent signals before making a decision.



 Architecture

The system uses an event-driven microservices architecture with Apache Kafka as the primary message broker.

┌─────────────────────────────────────────────────────────────┐
│                    EMAIL INGESTION                          │
│              Kafka Topic: emails.raw                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    PARSER SERVICE                           │
│       MIME parsing, extraction, storage to MinIO/S3         │
└─────────────────────────────────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    TEXT     │    │    HTML     │    │    IMAGE    │
│   Analyzer  │    │   Analyzer  │    │   Analyzer  │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                   │                  │
       └───────────────────┼──────────────────┘
                           ▼
              ┌───────────────────────┐
              │   LINK/META ANALYZER  │
              └───────────┬───────────┘
                          ▼
         ┌────────────────────────────────┐
         │       AGGREGATOR SERVICE       │
         │  Signal combination + scoring  │
         │  Campaign clustering (Redis)   │
         └────────────┬───────────────────┘
                      ▼
         ┌────────────────────────────────┐
         │        DECISION ENGINE         │
         │  Business rules + A/B testing │
         └────────────┬───────────────────┘
                      ▼
              ┌───────────────┐
              │    OUTPUT     │
              │   SIEM/SOAR   │
              └───────────────┘

For the complete architectural decision record, see:

ADR-001 — Event-Driven Architecture⁠￼



 Tech Stack

Category	Technology
Message Broker	Apache Kafka
Primary Database	PostgreSQL 15
Cache / State	Redis Cluster
Object Storage	MinIO / S3
Analytics Database	ClickHouse
ML Serving	NVIDIA Triton
Feature Store	Feast
Orchestration	Kubernetes + Istio
API Framework	FastAPI
Language	Python 3.11+
Observability	Prometheus, Loki, Tempo, Grafana



 Quick Start

Prerequisites

Before starting, make sure the following are installed:

* Docker
* Docker Compose
* Python 3.11+
* Git
* Make — optional



1. Clone the Repository

git clone https://github.com/your-org/ai-slop-detector.git
cd ai-slop-detector



2. Set Up the Python Environment

Create and activate a virtual environment:

python -m venv venv

macOS / Linux

source venv/bin/activate

Windows

venv\Scripts\activate

Install development dependencies:

pip install -r requirements-dev.txt

Install Git pre-commit hooks:

pre-commit install



3. Start Infrastructure

Start the local infrastructure:

docker-compose up -d

The development environment initializes:

Service	Port
Kafka	9092
PostgreSQL	5432
Redis	6379
MinIO API	9000
MinIO Console	9001



4. Run a Service

For example, start the parser service:

cd services/parser
uvicorn main:app --reload --port 8001

The health endpoint should be available at:

http://localhost:8001/health



5. Run Tests

pytest tests/unit/ -v



 Documentation

Document	Description
Getting Started⁠￼	Complete setup guide for new developers
Architecture⁠￼	Architecture documentation and ADRs
API Reference⁠￼	REST and gRPC API documentation
Deployment Guide⁠￼	Production deployment procedures
Monitoring⁠￼	Observability and monitoring setup
Troubleshooting⁠￼	Common problems and solutions
Security⁠￼	Security policy and vulnerability reporting
Contributing⁠￼	Contribution and development guidelines

⸻

 Development

Code Quality

Format the code:

make format

Run linters:

make lint

Run the complete test suite:

make test



Commit Convention

The project follows Conventional Commits.

General format:

<type>(<scope>): <description>

Examples:

feat(parser): add MIME multipart parsing
fix(text-analyzer): handle empty email bodies
docs(api): update endpoint documentation

Allowed Types

* feat — new feature
* fix — bug fix
* docs — documentation
* style — code style changes
* refactor — code restructuring
* test — tests
* chore — maintenance
* perf — performance improvements
* ci — CI/CD changes
* build — build system changes



 Project Structure

ai-slop-detector/
│
├── services/                  # Microservices
│   ├── parser/               # Email parsing
│   ├── text-analyzer/        # Text analysis
│   ├── html-analyzer/        # HTML analysis
│   ├── image-analyzer/       # Image analysis
│   ├── link-analyzer/        # Link analysis
│   ├── aggregator/           # Signal aggregation
│   └── decision-engine/      # Final classification
│
├── shared/                    # Shared components
│   ├── models/               # Pydantic schemas
│   ├── proto/                # gRPC definitions
│   └── utils/                # Shared utilities
│
├── ml/                        # Machine Learning
│   ├── training/             # Model training
│   ├── models/               # Trained models
│   └── feature-store/        # Feature definitions
│
├── infra/                     # Infrastructure as Code
│   ├── terraform/             # Terraform configuration
│   ├── helm/                  # Kubernetes Helm charts
│   └── docker/                # Docker configuration
│
├── tests/                     # Test suites
│   ├── unit/
│   ├── integration/
│   └── load/
│
└── docs/                      # Project documentation
    ├── architecture/
    ├── api/
    └── runbooks/



 Testing

Unit Tests

Run unit tests with coverage:

pytest tests/unit/ -v --cov=services --cov=shared

Integration Tests

Integration tests require the Docker Compose infrastructure:

pytest tests/integration/ -v

Load Testing

Run load tests using Locust:

locust -f tests/load/locustfile.py --host=http://localhost:8001



 Performance Targets

The initial production targets are:

Metric	Target
Throughput	10,000 emails/second
p95 Latency	< 2 seconds
Availability	99.9%
Error Rate	< 1%

These targets are intended to guide architectural and infrastructure decisions as the project evolves.



Deployment

Kubernetes

Install or upgrade the application using Helm:

helm upgrade --install ai-slop-detector ./infra/helm \
  --namespace ai-slop-detector \
  --create-namespace \
  --set image.tag=v0.1.0



Terraform

For AWS or GCP infrastructure:

cd infra/terraform
terraform init
terraform plan
terraform apply

For complete deployment instructions, see:

Deployment Guide⁠￼



 Roadmap

Phase 1 — Core Infrastructure

Current

* Project structure
* Microservices scaffolding
* Shared models
* Local development environment
* Parser service implementation
* Basic text analyzer



Phase 2 — ML Models

* Style clash detection model
* HTML anomaly detection
* Image artifact detection
* Campaign clustering using DBSCAN + GNN



Phase 3 — Production Deployment

* Kubernetes deployment
* CI/CD pipeline using GitLab CI
* Monitoring and alerting
* Large-scale load testing



Phase 4 — Advanced Features

* Real-time campaign detection
* A/B testing framework
* Shadow mode for new models
* SOC integration playbooks
* Threat Intelligence integration



 Contributing

Contributions are welcome.

Before submitting changes, please review the:

Contributing Guide⁠￼

The guide contains information about:

* development workflow;
* branch conventions;
* pull requests;
* code style;
* testing requirements.

Security Issues

Please do not open public GitHub issues for security vulnerabilities.

Instead, follow the process described in:

Security Policy⁠￼



 License

This project is licensed under the GNU General Public License v3.0.

See the LICENSE⁠￼ file for the complete license text.

Copyright (C) 2026 AI-Slop-detector Authors
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.



 Support

If you need help with the project, use the following resources:

* Documentation: docs/⁠￼
* Issues: ⁠GitHub Issues
* Discussions: ⁠GitHub Discussions
* Security: m.gavrilenko@g.nsu.ru


 Project Status

Current version: v0.1.0

Status: 🚧 Active Development

The project is currently focused on implementing the core infrastructure and initial detection services. Advanced ML capabilities and production deployment features are planned for subsequent development phases.

