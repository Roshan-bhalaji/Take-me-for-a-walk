# Take Me For A Walk

## Overview

"Take Me For A Walk" is a web application that provides users with customized walking routes based on their preferences. The app uses Google Maps API and other geolocation services to generate walking paths tailored to the user's location and preferences, such as landmarks, difficulty levels, and route avoidance options.

## Features

- **Custom Route Generation:** Generate routes based on user-selected landmarks, mode of transportation (walking or driving), and desired time duration.
- **Geolocation:** Automatically detects and uses the user's current location.
- **Map Visualization:** Displays the selected route on an interactive map with detailed route information.
- **Dynamic Difficulty Adjustment:** Customize the difficulty level of the walking path based on elevation changes.

## Prerequisites

Before you can run the application, make sure you have the following installed:

- Python 3.7 or higher
- Necessary environment variables configured (explained below)

## Installation

1. **Clone the Repository**
    ```bash
    git clone https://github.com/yourusername/takemeforawalk.git
    cd takemeforawalk
    ```

2. **Create and Activate a Virtual Environment**
    ```bash
    python -m venv venv
    source venv/bin/activate   # On Windows, use `venv\Scripts\activate`
    ```

3. **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4. **Set Up Environment Variables**

    Create a `.env` file in the root directory of your project and add the following variables:

    ```plaintext
 
    APP_PASSWORD=your_app_password
    GOOGLE_MAPS_API_KEY=your_google_maps_api_key
    ```

    Replace `your_email@gmail.com`, `your_app_password`, and `your_google_maps_api_key` with your actual credentials and API key.

## Running the Application

To run the application, navigate to the project directory and execute the following command:

```bash
python -m streamlit run app.py
