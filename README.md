# QoSentry – Intelligent Network Monitoring Platform

## Overview
This project was developed as part of the **PIDEV – 4th Year Engineering Program DS speciality** at **Esprit School of Engineering** (Academic Year 2025–2026).

**QoS-Sentry** is an intelligent, platform-agnostic solution designed to shift network management from a "reactive cycle of firefighting" to a proactive, AI-driven approach. By combining Network Engineering, Data Science, and Generative AI, the platform addresses critical issues such as alert fatigue, static threshold management, and the lack of predictive insights in traditional monitoring tools.

## Features
- **Predictive Analytics:** Anticipating SLA breaches before they impact end-users using time-series forecasting.
- **Risk-Free Simulation:** A "Digital Twin" sandbox environment (Mininet/SDN) to test configuration changes safely.
- **Intelligent Automation:** Reducing manual intervention via reinforcement learning-based recommendations.
- **RAG-Powered Intelligibility:** A specialized **QoS-Buddy** agent that uses Retrieval-Augmented Generation (RAG) to translate complex technical logs into actionable executive summaries.
- **Explainability-First Design (XAI):** Clear attribution and explanation for AI-driven decisions to ensure human-in-the-loop control.

## Tech Stack

### Frontend
- **Next.js:** For a high-performance, responsive web dashboard.
- **Tailwind CSS:** For role-adaptive user interface design.

### Backend
- **Spring Boot:** Orchestration layer handling business logic and service communication.
- **FastAPI:** Powering the AI microservices (Agent & RAG).
- **Qdrant:** Vector database for high-efficiency semantic search and RAG.
- **Redis:** For real-time metrics caching and Pub/Sub telemetry streams.
- **PostgreSQL:** Relational database for persistence layer.
- **Ryu SDN Controller:** For Software-Defined Networking management and flow control.

### AI/ML & Infrastructure
- **PyTorch** For high-performance deep learning model training and inference.
- **LangChain & LangGraph:** Orchestrating the "QoSentry" agentic workflow.
- **Mininet:** Network emulation for the experimental testbed.

## Architecture
QoS-Sentry follows a **microservices architecture** designed for scalability and modularity, composed of five distinct layers:
1.  **Presentation Layer:** Next.js Dashboard for User Interface.
2.  **Orchestration Layer:** Spring Boot API Gateway.
3.  **Monitoring Layer:** Prometheus & Grafana for metric collection and visualization.
4.  **Simulation Layer:** Mininet VM for topology emulation.
5.  **AI Intelligence Layer:** Specialized services for Prediction, Anomaly Detection, and RAG Reporting.

## Contributors
- **Khayat Mohamed** – Project Lead
- **Mezzi Rawen** – Project Manager
- **Farhani Hamza** – Data Scientist
- **Ben M’sahel Wiem** – Data Scientist
- **Najar Koussay** – Data Scientist
- **Krid Taoufik** – Solution Architect

## Academic Context
Developed at **Esprit School of Engineering – Tunisia**
**PIDEV – 4DS | 2025–2026**

## Acknowledgments
- Inspired by the **Team Data Science Process (TDSP)** methodology.
- Special thanks to the faculty at **Esprit School of Engineering** for their guidance and resources.
- Built using **Mininet** and **Ryu SDN Controller** for realistic network simulation.
