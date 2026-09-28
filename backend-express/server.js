// Load environment variables first
require("dotenv").config();

const express = require("express");
const cors = require("cors");
const Groq = require("groq-sdk");
const pool = require("./db");

const app = express();
const PORT = process.env.PORT || 5000;

// Initialize Groq using the API key stored in .env
const groq = new Groq({
  apiKey: process.env.GROQ_API_KEY,
});

// Middleware
app.use(cors());
app.use(express.json());

// --------------------------------------------------
// 1. ROOT API
// --------------------------------------------------

app.get("/", (req, res) => {
  res.json({
    message: "Manufacturing Quality Memory Agent API is running",
  });
});

// --------------------------------------------------
// 2. API HEALTH CHECK
// --------------------------------------------------

app.get("/api/health", (req, res) => {
  res.json({
    status: "ok",
    message: "Node.js + Express API is running",
  });
});

// --------------------------------------------------
// 3. DATABASE HEALTH CHECK
// --------------------------------------------------

app.get("/api/db-health", async (req, res) => {
  try {
    const [rows] = await pool.query("SELECT 1 AS database_connected");

    res.json({
      status: "ok",
      message: "MySQL connection successful",
      database: rows[0].database_connected === 1,
    });
  } catch (error) {
    console.error("Database health check failed:", error.message);

    res.status(500).json({
      status: "error",
      message: "Unable to connect to MySQL",
    });
  }
});

// --------------------------------------------------
// 4. GET ALL QUALITY INCIDENTS
// --------------------------------------------------

app.get("/api/incidents", async (req, res) => {
  try {
    const [rows] = await pool.execute(`
      SELECT
        id,
        incident_code,
        title,
        description,
        defect_category,
        severity,
        status,
        root_cause,
        corrective_action,
        created_at
      FROM quality_incidents
      ORDER BY created_at DESC
    `);

    res.json({
      total: rows.length,
      items: rows,
    });
  } catch (error) {
    console.error("Get incidents error:", error.message);

    res.status(500).json({
      error: "Unable to retrieve quality incidents",
    });
  }
});

// --------------------------------------------------
// 5. CREATE A QUALITY INCIDENT
// --------------------------------------------------

app.post("/api/incidents", async (req, res) => {
  try {
    const {
      incident_code,
      title,
      description,
      defect_category,
      severity,
      status,
      root_cause,
      corrective_action,
    } = req.body;

    // Required field validation
    if (
      !incident_code ||
      !title ||
      !description
    ) {
      return res.status(400).json({
        error: "Incident code, title, and description are required.",
      });
    }

    const [result] = await pool.execute(
      `
      INSERT INTO quality_incidents (
        incident_code,
        title,
        description,
        defect_category,
        severity,
        status,
        root_cause,
        corrective_action
      )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `,
      [
        incident_code,
        title,
        description,
        defect_category || "Manufacturing Defect",
        severity || "Medium",
        status || "Open",
        root_cause || null,
        corrective_action || null,
      ]
    );

    res.status(201).json({
      message: "Quality incident created successfully",
      id: result.insertId,
      incident_code,
    });
  } catch (error) {
    console.error("Create incident error:", error.message);

    // Duplicate incident code
    if (error.code === "ER_DUP_ENTRY") {
      return res.status(409).json({
        error: "This incident code already exists.",
      });
    }

    res.status(500).json({
      error: "Unable to create quality incident",
    });
  }
});

// --------------------------------------------------
// 6. GROQ AI - SIMILAR INCIDENT SEARCH
// --------------------------------------------------

app.post("/api/ai/similar-incidents", async (req, res) => {
  try {
    const { query } = req.body;

    // Validate input
    if (typeof query !== "string" || !query.trim()) {
      return res.status(400).json({
        error: "Please provide a defect description.",
      });
    }

    // Retrieve saved incidents from MySQL
    const [incidents] = await pool.execute(`
      SELECT
        incident_code,
        title,
        description,
        defect_category,
        severity,
        status,
        root_cause,
        corrective_action
      FROM quality_incidents
      ORDER BY created_at DESC
      LIMIT 100
    `);

    if (incidents.length === 0) {
      return res.json({
        answer: "No saved quality incidents are available to compare.",
      });
    }

    // Ask Groq to compare the new defect with saved incidents
    const completion = await groq.chat.completions.create({
      model: "llama-3.3-70b-versatile",
      temperature: 0.2,
      messages: [
        {
          role: "system",
          content: `
You are a Manufacturing Quality Memory Assistant.

Your task is to compare a new manufacturing defect description
with previously saved quality incidents.

Instructions:
1. Identify incidents that may be related to the new defect.
2. Include the incident code for each relevant record.
3. Summarize the recorded root cause and corrective action.
4. Explain briefly why the incident may be related.
5. Use only the supplied incident records.
6. Never invent incident codes, root causes, or corrective actions.
7. If no incidents are relevant, clearly say so.
8. Treat missing root causes or corrective actions as "Not recorded".
9. Present the answer in clear, simple language for a quality engineer.
          `,
        },
        {
          role: "user",
          content: `
New defect description:
${query}

Saved quality incidents:
${JSON.stringify(incidents, null, 2)}

Find potentially related incidents and summarize their recorded
root causes and corrective actions.
          `,
        },
      ],
    });

    const answer =
      completion.choices[0]?.message?.content ||
      "No AI response was generated.";

    res.json({
      answer,
      compared_incidents: incidents.length,
    });
  } catch (error) {
    console.error("Groq similar-incidents error:", error.message);

    res.status(500).json({
      error: "Unable to search similar incidents using AI.",
    });
  }
});

// --------------------------------------------------
// 7. START EXPRESS SERVER
// --------------------------------------------------

app.listen(PORT, () => {
  console.log(`Express server running on http://localhost:${PORT}`);
});