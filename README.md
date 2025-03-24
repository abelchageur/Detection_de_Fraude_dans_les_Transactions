# **Projet de Détection de Fraude en Quasi Temps Réel**

## **1. Contexte du Projet**
En tant que développeur Data, l'objectif de ce projet est de détecter en quasi temps réel les activités suspectes tout en minimisant les fausses alertes.  

Le projet comprend :  
- Le développement d'API pour l'accès aux données de transactions, clients et sources externes.  
- La collecte et l'intégration des données.  
- Le stockage et la gestion des données avec Hive.  
- Le développement d'un système de détection de fraude basé sur des règles.  
- L'orchestration avec Airflow et CI/CD.  
- **L'utilisation de Docker Compose pour le déploiement de tous les services.**  

---

## **2. Développement des API**
### **2.1 API des Données de Transaction**
- Endpoint : `/api/transactions`
- Données fournies :  
  - ID de transaction  
  - Date et heure  
  - Montant et devise  
  - Détails du commerçant  
  - ID du client  
  - Type de transaction  

### **2.2 API des Données Client**
- Endpoint : `/api/customers`
- Données fournies :  
  - ID client  
  - Historique des comptes  
  - Informations démographiques  
  - Modèles comportementaux  

### **2.3 API des Données Externes**
- Endpoint : `/api/externalData`
- Données fournies :  
  - Informations de liste noire  
  - Scores de crédit  
  - Rapports de fraude  

---

## **3. Collecte et Intégration des Données**
- Utilisation des API développées pour collecter les données transactionnelles, clients et externes.  
- Assurer la qualité des données (nettoyage et transformation).  
- Stockage des données dans un format adapté pour l'analyse.  

---

## **4. Stockage et Gestion des Données avec Hive**
- Conception et mise en place de tables Hive pour stocker les données.  
- Application de stratégies de **partitionnement** et **bucketting** pour améliorer les performances des requêtes.  

---

## **5. Développement du Système de Détection de Fraude**
### **5.1 Règles de Détection de Fraude avec HiveQL**
Exemples de règles implémentées :  
- **Montants anormalement élevés** : Détection des transactions supérieures à un seuil défini.  
- **Fréquence élevée** : Identification des clients effectuant un nombre inhabituel de transactions sur une courte période.  
- **Localisation inhabituelle** : Transactions effectuées depuis un lieu non habituel pour le client.  
- **Liste noire** : Transactions impliquant des clients figurant sur une liste noire.  

---

## **6. Déploiement avec Docker Compose**
Tous les services sont déployés à l'aide de **Docker Compose** pour assurer une infrastructure modulaire et facile à gérer.  

### **6.1 Services Déployés**
- **API des Transactions, Clients et Données Externes** (Flask)  
- **Hive et Hadoop** pour le stockage des données  
- **Airflow** pour l'orchestration des workflows  
- **PostgreSQL** comme backend de Metastore Hive et Airflow  


1. **Cloner le projet**  
   ```bash
   git clone https://github.com/votre-repo.git
   cd votre-repo
   
2. **Démarrer les services avec Docker Compose**
   ```bash
   docker-compose up -d

3. **Vérifier les logs des services**
   ```bash
   docker-compose logs -f
