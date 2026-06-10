import React from 'react';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1>CBDC Fraud Detection Dashboard</h1>
        <p>Real-time monitoring and analytics for federated fraud detection.</p>
      </header>
      <main>
        <div className="stats-container">
          <div className="card">
            <h3>Total Transactions</h3>
            <p>0</p>
          </div>
          <div className="card">
            <h3>Fraud Alerts</h3>
            <p>0</p>
          </div>
          <div className="card">
            <h3>Model Accuracy</h3>
            <p>0.00%</p>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
