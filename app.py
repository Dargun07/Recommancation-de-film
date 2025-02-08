import streamlit as st
from streamlit_option_menu import option_menu
import random
from tmdbv3api import TMDb, Movie, Discover
from IPython.display import Image
from PIL import Image
import requests

from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import pandas as pd
import re

tmdb = TMDb()
tmdb.api_key = '59fa21d4a3485aae1e53d7cb4c21883e'
tmdb.language = "fr"

# Load the image
image = Image.open("logo.png") 

# Create a container
container = st.container()

with container:
    col1, col2 = st.columns([1, 2]) 
    with col1:
        st.image(image)
    with col2:
        st.title("Projet 2 Moving Frame") 
    
with st.sidebar :
    st.title("La région cible") 
    st.image("creuse.png")
    st.write("La mise en place du système de recommandation de films est faite pour le compte de notre client, gérant de cinéma dans la Creuse pour lui permettre de sélectionner des films pour ses clients locaux. ") 
    
    st.subheader("Contactez-nous")
    with st.form("reply_form"):
        name = st.text_input("Nom")
        email = st.text_input("Email")
        phone = st.text_input("Téléphone")
        message = st.text_area("Ecrivez votre message")
        submitted = st.form_submit_button("Envoyer")
        if submitted:
            st.success("Mercie pour votre réponse!")

    st.subheader("Laissez-nous un commentaire")
    with st.form("comment_form"):
        comment = st.text_area("Votre commentaire")
        submitted = st.form_submit_button("Poster")
        if submitted:
            st.success("Commentaire est posté avec succès!") 

selection = option_menu(
        menu_title=None,
        options=["Accueil", "Recherche", "Notre Équipe", "Notre Site"],
        icons=["🏠", "🔭", "📷", "🖼️"],
        menu_icon="menu-app",
        default_index=0,
        orientation="horizontal",
    )

# Affichage du contenu en fonction de la sélection
if selection == "Accueil":
    st.write("# Bienvenue sur notre site!")

    st.write(""" 
        **Moving Frame vous présente les films à la Une.**
        
        Vous ne trouvez pas votre bonheur ? Pas de soucis ! Nous nous adaptons à vos envies.
        Passez à la page de recommandations.
    """)
  
    # Initialize the Discover class
    discover = Discover()

    # Search for popular movies using the Discover object
    search_results = discover.discover_movies({"sort_by": "popularity.desc"})

    # Convert search_results to a list (if not already a list)
    search_results_list = list(search_results)

    # Ensure there are at least 10 movies to sample
    if len(search_results_list) < 10:
        print("Not enough movies to sample.")
    else:
        # Randomly select 10 movies from the results
        random_movies = random.sample(search_results_list, 6)

        # Initialize the Movie class for fetching details
        movie_search = Movie()

        movies = []
        # Loop through the selected movies and display their details
        for movie in random_movies:
            movie_id = movie.id
            # Get movie details
            movie_details = movie_search.details(movie_id)
            movies.append(movie.title)

    # Fonction pour récupérer l'image du film
    def get_movie_poster(movie_name):
          movie_search = Movie()
          search_results = movie_search.search(movie_name)  # Rechercher le film
          if search_results:
              movie_id = search_results[0].id
              movie_details = movie_search.details(movie_id)
              poster_path = movie_details.poster_path
              if poster_path:
                  return f"https://image.tmdb.org/t/p/w500/{poster_path}"
          return None

    # Télécharger et afficher les images
    cols = st.columns(3)  # Diviser l'écran en 3 colonnes
    for i, movie_name in enumerate(movies):
        with cols[i % 3]:  # Répartir les films dans les colonnes
            poster_url = get_movie_poster(movie_name)
            if poster_url:
                st.image( poster_url,caption=movie_name)
            else:
                st.write("Affiche non disponible")

elif selection == "Recherche": 

    # Load Data
    @st.cache_data
    def load_data():
        return pd.read_parquet('data.parquet')  # Replace with your file path

    df = load_data()

    # Prepare Data
    @st.cache_data
    def prepare_data(df):
        # TF-IDF for text columns
        text_cols = ['overview', 'title', 'original_title', 'production_companies_name', 'actor', 'director']
        tfidf_vectors = [TfidfVectorizer(max_features=500).fit_transform(df[col].fillna('')).toarray() for col in text_cols]
        tfidf_combined = np.hstack(tfidf_vectors)

        # One-hot encoding for categorical columns
        cat_cols = ['genres', 'original_language', 'production_countries', 'spoken_languages']
        one_hot_encoded = pd.get_dummies(df[cat_cols], columns=cat_cols).values

        # Scaled numerical columns
        num_cols = ['budget', 'popularity', 'revenue', 'runtime', 'vote_average', 'vote_count']
        num_scaled = StandardScaler().fit_transform(df[num_cols])

        return np.hstack([tfidf_combined, one_hot_encoded, num_scaled])

    X_combined = prepare_data(df)

    # Train KNN Model
    @st.cache_resource
    def train_knn(X_combined):
        model = NearestNeighbors(metric='cosine', algorithm='brute')
        model.fit(X_combined)
        return model

    knn_model = train_knn(X_combined)

    # Get Movie Poster and Comment
    def get_movie_poster(movie_name):
        movie_search = Movie()
        search_results = movie_search.search(movie_name)
        if search_results:
            movie_id = search_results[0].id
            movie_details = movie_search.details(movie_id)
            poster_path = movie_details.poster_path
            if poster_path:
                return f"https://image.tmdb.org/t/p/w500/{poster_path}"
        return None

    def get_movie_comment(movie_name):
        movie_search = Movie()
        search_results = movie_search.search(movie_name)
        if search_results:
            movie_id = search_results[0].id
            url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={tmdb.api_key}&language={tmdb.language}"
            response = requests.get(url)
            if response.status_code == 200:
                return response.json().get('overview', 'Aucun résumé disponible.')
        return "Résumé non disponible."

    # Recommend Movies
    def recommend_movies(movie_id, top_n=5):
        try:
            idx = df[df['imdb_id'] == movie_id].index[0]
            distances, indices = knn_model.kneighbors(X_combined[idx].reshape(1, -1), n_neighbors=top_n + 1)
            recommendations = df.iloc[indices.flatten()[1:]]
            return recommendations[['imdb_id', 'title', 'poster_url', 'genres', 'actor', 'director']].drop_duplicates()
        except IndexError:
            return None

    # Streamlit UI
    st.title("Recommandation de films")
    search_type = st.radio("Rechercher par :", ["Titre", "Acteur(trice)"])

    # Search input
    query = st.text_input(f"Entrez un {search_type.lower()} du film", "")
    if st.button(f"Recommander des films par un {search_type.lower()}"):
        if not query.strip():
            st.warning(f"Veuillez entrer un(e) {search_type.lower()}.")
        else:
            with st.spinner("Recherche en cours..."):
                # Filter DataFrame (ensure 'df' has 'title' column)
                if search_type == "Titre":
                    matching_movies = df[df['title'] == query]
                else:
                    matching_movies = df[df['actor'].str.contains(query, case=False, na=False)]

            if matching_movies.empty:
                st.error(f"Aucun film trouvé pour ce {search_type.lower()}.")
            else:
                if search_type == "Titre":
                    # Dropdown for title matches
                    movie_titles = matching_movies['title'].tolist()
                    selected_movie = matching_movies[matching_movies['title'] == movie_titles].iloc[0]
                    
                    st.write(f"Recommandations pour : **{selected_movie['title']}**")
                    recommended_movies = recommend_movies(selected_movie['imdb_id'])

                else:
                    # Dropdown for actor matches
                    actor_movies = matching_movies[['title', 'actor']].drop_duplicates()
                    selected_title = actor_movies['title'].tolist()

                    selected_movie = matching_movies[matching_movies['title'] == selected_title].iloc[0]

                    # Display other movies by the same actor
                    selected_actor = query
                    st.write(f"Recommandations pour : **{selected_actor}**")
                    recommended_movies = df[df['actor'].str.contains(selected_actor, case=False, na=False)]
                    recommended_movies = recommended_movies[recommended_movies['title'] != selected_movie['title']]

                # Display recommendations
                if not recommended_movies.empty:
                    for _, movie in recommended_movies.iterrows():
                        poster_url = get_movie_poster(movie['title'])
                        comment = get_movie_comment(movie['title'])

                        col1, col2 = st.columns([1, 2])
                        with col1:
                            if poster_url:
                                st.image(poster_url, caption=movie['title'])
                            else:
                                st.write("Affiche non disponible")
                        with col2:
                            st.write(f"**{movie['title']}**")
                            st.write(comment)
                else:
                    st.error("Impossible de générer des recommandations pour ce film.")

elif  selection == "Notre Équipe":
   
  # Load the image
  image1 = Image.open("IMG_1.jpg") 
  image2 = Image.open("IMG_2.jpg") 
  image3 = Image.open("IMG_3.jpg") 
  image4 = Image.open("IMG_4.jpg") 

  st.write("""
          Rencontrez l’équipe talentueuse derrière notre succès :
      """)

# Create a container for the title and image
  col1, col2 = st.columns([1, 2])
  with col1:
    st.image(image4)
  with col2:
    st.markdown("**Jean Alain Delobelle** : Responsable des études de marché")

# Create a container for the title and image
  col3, col4 = st.columns([1, 2])
  with col3:
    st.image(image3)
  with col4:
    st.markdown(
        "**Laetitia Palogo** : Chef de produit <br>"
        "(En contact avec le client et l'équipe marketing)", 
        unsafe_allow_html=True
    )

# Create a container for the title and image
  col5, col6 = st.columns([1, 2])
  with col5:
    st.image(image2)
  with col6:
    st.markdown(
        "**Sopanha SAO** : Data Analysts <br>"
        "(En contact avec l'équipe commerciale et le service financier)", 
        unsafe_allow_html=True
    )

# Create a container for the title and image
  col7, col8 = st.columns([1, 2])
  with col7:
    st.image(image1)
  with col8:
    st.markdown(
        "**Riad Souyad** : Data Analysts <br>"
        "(En contact avec le service technique et l'équipe juridique (si nécessaire))", 
        unsafe_allow_html=True
    )

elif  selection == "Notre Site":
   
    image5 = Image.open("groupe.jpg") 
    st.image(image5) 

    st.write("Habitants de la creuse, grâce à ce site vous aurez un cinéma qui s’adapte à vous, à vos envies du moment. Alors n’attendez-plus, testez !")
