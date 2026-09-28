require("dotenv").config();

const pool = require("./db");

async function testConnection() {
  try {
    const [rows] = await pool.query("SELECT DATABASE() AS databaseName");
    console.log("MySQL connection successful!");
    console.log("Connected database:", rows[0].databaseName);
  } catch (error) {
    console.error("MySQL connection failed:", error.message);
  } finally {
    await pool.end();
  }
}

testConnection();