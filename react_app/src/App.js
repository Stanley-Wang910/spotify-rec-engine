import React, { useState, useEffect } from "react";
import Login from "./components/Login";
import SearchBar from "./components/SearchBar";
import RecommendationsList from "./components/RecommendationList";
import Logout from "./components/Logout";
import "./App.css";

function App() {
  const [token, setToken] = useState("");
  const [recommendations, setRecommendations] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    async function getToken() {
      const response = await fetch("/auth/token");
      const json = await response.json();
      setToken(json.access_token);
    }

    getToken();
  }, []);

  const handleRecommendations = (data) => {
    setRecommendations(data);
  };

  return (
    <div className="App bg-custom_dark">
      <div className="App-content flex-col justify-center items-center min-h-screen relative">
        {token === "" ? (
          <Login />
        ) : (
          <div className="main-container max-w-2xl w-full mx-auto p-4">
            <Logout
                setToken={setToken}
                setRecommendations={setRecommendations}
            />
            {/* <div className="image-container w-full h-1/2 flex justify-center items-center mb-8">
              <img src="/049285ff-1e57-4ef7-b30e-6e53cc1edafb.jpg" alt="Descriptive Alt Text" className="w-full h-full object-cover" />
            </div> */}
            <div className="flex flex-col items-center">
              <div className="search-container mb-2 w-full max-w-lg">
                <SearchBar onRecommendations={handleRecommendations}setIsLoading={setIsLoading} />
              </div>
              <div className="recommendations-container w-full flex items-center justify-start mt-4">
                {isLoading ? (
                  <div className="loader">
                    <div className="bar1"></div>
                    <div className="bar2"></div>
                    <div className="bar3"></div>
                    <div className="bar4"></div>
                    <div className="bar5"></div>
                    <div className="bar6"></div>
                  </div>
                ) : (
                  <RecommendationsList recommendations={recommendations} />
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;