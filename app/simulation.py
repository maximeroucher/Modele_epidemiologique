from __future__ import print_function

import math
import os
import random
import sqlite3
import time
import datetime
from enum import Enum

from tqdm import tqdm

from tools import *

# Mute l'import de pygame
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = 'True'
# Postionne la fenêtre de l'application
os.environ['SDL_VIDEO_WINDOW_POS'] = "0,0"

import pygame

colors = [pygame.Color(20, 100, 255), pygame.Color(255, 100, 20), pygame.Color(100, 100, 100)]


class Etat(Enum):
    SAIN = 1
    INFECTE = 2
    RETABLI = 3


class Comportement(Enum):
    NORMAL = 1
    QUARANTAINE = 2
    DEPLACEMENT = 3
    CONFINEMENT = 4

    def __str__(self):
        return self._name_.capitalize()


class Person:

    def __init__(self, id, x, y, vx, vy, ax, ay, p, rayon):
        """ Initialisation de la personne
        ---
        param :

            - id (int) l'identifiant de la personne
            - x (int) la position en absisce
            - y (int) la position en ordonnée
            - vx (float) la vitesse en absisce
            - vy (float) la vitesse en ordonnée
            - ax (float) l'accélération en absisce
            - ay (float) l'accélération en ordonnée
            - p (float 0 <= p <= 1) la probabilité de contaminer une personne
        """
        self.id = id
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.ax = ax
        self.ay = ay
        self.p = p
        self.TPS_INFECTE = random.randint(40, 60)
        self.etat = Etat.SAIN
        self.comportement = Comportement.NORMAL
        self.VMAX = 5
        self.RAYON = rayon
        self.f = 1
        self.k = 1


    def __eq__(self, other):
        """ Égalité entre deux personnes
        ---
        param :

            - other (Person) la personne dont on veut vérifier si c'est l'autre
        """
        return self.id == other.id


    def correction_vitesse(self):
        """ Renormalise la vitesse si elle dépasse la vitesse maximale
        ---
        """
        v = self.vx ** 2 + self.vy ** 2
        if v > self.VMAX ** 2:
            r = self.VMAX / math.sqrt(v)
            self.vx *= r
            self.vy *= r


    def mise_a_jour(self, w, h, person):
        """ Calcul de l'étape suivante
        ---
        param :

            - w (int) la largeur de l'espace de simulation
            - h (int) la hauteur de l'espace de simulation
            - person (list(Person)) la liste des personnes de la simulation
        """
        self.ax = self.ay = 0
        if self.comportement == Comportement.QUARANTAINE:
            self.repulsion(person)
        self.vx += self.ax
        self.vy += self.ay
        self.correction_vitesse()
        if self.x > w or self.x < 0:
            self.vx = - self.vx
        if self.y > h or self.y < 0:
            self.vy = - self.vy
        self.x += int(self.vx)
        self.y += int(self.vy)
        if self.etat == Etat.INFECTE:
            self.TPS_INFECTE -= 1
        if self.TPS_INFECTE == 0:
            self.etat = Etat.RETABLI


    def repulsion(self, person):
        """ Calcule une force de répulsion entre les autres particules et celle-ci, dans le cas d'un confinement
        ---
        param :

            - person (list(Person)) la liste des personnes de la simulation
        """
        ax = ay = 0
        for other in person:
            if other is not self:
                dx = abs(self.x - other.x)
                if dx < 5 * self.RAYON:
                    dy = abs(self.y - other.y)
                    if dy < 5 * self.RAYON:
                        angle = math.atan2(self.y - other.y, self.x - other.x)
                        d = math.hypot(dy, dx)
                        v = math.hypot(self.vx, self.vy)
                        f = self.k * (d - 2 * self.RAYON) - self.f * v
                        ax += f * math.cos(angle)
                        ay += f * math.sin(angle)
        self.ax = ax
        self.ay = ay


    def couleur(self):
        """ Indique la couleur d'affichage en fonction de l'état
        ---
        result :

            - pygame.Color
        """
        if self.etat == Etat.SAIN:
            return colors[0]
        elif self.etat == Etat.INFECTE:
            return colors[1]
        return colors[2]


    def collision(self, other):
        """ Vérifie s'il y a collision
        ---
        """
        dx = self.x - other.x
        if dx < 1.5 * 2 * self.RAYON:
            dy = self.y - other.y
            if dy < 1.5 * 2 * self.RAYON:
                return dx ** 2 + dy ** 2 <= 3 * 4 * self.RAYON ** 2
            return False
        return False


    def afficher(self, screen, t):
        """ Affiche la personne
        ---
        param :

            - screen (pygame.Surface) l'écran
            - t (int) la distance au bord supérieur de la fenêtre
        """
        pygame.draw.circle(screen, self.couleur(), (self.x, self.y + t), self.RAYON)


    def copier(self):
        """ Retourne une copie de la persoone
        ---
        """
        return Person(self.id, self.x, self.y, self.vx, self.vy, self.ax, self.ay, self.p, self.RAYON)


class Simulation:

    def __init__(self, person, w, h, screen, top, taux_incidence, threshold, comportement_urgence=Comportement.QUARANTAINE):
        """ Initialisation de la simulation
        ---
        param :

            - person (list(Person)) la liste de personne de la simulation
            - w (int) la largeur de l'espace de la simulation
            - h (int) la hauteur de l'espace de la simulation
            - screen (Pygame.Surface) la surface sur laquelle afficher la simulation
            - top (int) la distance au haut de la fenêtre
            - taux_incidence (int) le nombre de personnes infectés simultanément avant de mettre en place une quarantaine
            - threshold (float 0 <= threshold <= 1) le pourcentage de taux_incidence à atteindre afin de mettre fin à la quarantaine
            - comportement_urgence (Comportement) le comportement de la simulation si le nombre d'inféctés est supérieur à taux_incidence
        """
        self.person = [Person.copier(p) for p in person]
        self.person[0].etat = Etat.INFECTE
        self.sains = self.person[0:-1]
        self.infectes = [self.person[0]]
        self.retablis = []
        self.w = w
        self.h = h
        self.y = [0]
        self.data = {"Sains": [], "Infectés": [], "Rétablis": []}
        self.data_font = pygame.font.SysFont("montserrat", 18)
        self.font = pygame.font.SysFont("montserrat", 24)
        self.reassignation()
        self.mise_a_jour_donnees()
        self.screen = screen
        self.comportement = Comportement.NORMAL
        self.TAUX_INCIDENCE = taux_incidence
        self.quarantine_time = []
        self.threshold = threshold

        # Largeur de la fenêtre
        self.WIDTH = 700
        # Hauteur de la fenêtre
        self.HEIGHT = 390
        # Marge entre les bords de la fenêtre et le graphique
        self.MARGIN = 30
        # Hauteur maximale du graphique
        self.HAUT = self.HEIGHT - self.MARGIN
        # Longeur d'un trait
        self.DHAUT = self.HAUT + 5
        # La largeur du graphique
        self.W = self.WIDTH - 2 * self.MARGIN
        # la hauteur du grpahique
        self.H = self.HEIGHT - 2 * self.MARGIN
        # La distance au haut de la fenêtre
        self.TOP = top
        # La distance à gauche du graphique du pays
        self.LEFT = 1100
        self.no_action = taux_incidence == 0
        self.ended = False
        self.comportement_urgence = comportement_urgence


    def initialisation_affichage(self):
        """ Initialisation de l'affichage de la simulation
        ---
        """
        if self.no_action:
            center_text(self.screen, self.data_font, "Aucunes mesures", FG, 500, 20, self.TOP - 30, 1200)
        for x, key in enumerate(self.data):
            pygame.draw.line(
                self.screen, colors[x],
                (1150 + 250 * x, self.TOP + 440),
                (1250 + 250 * x, self.TOP + 440),
                2)
            center_text(self.screen, self.font, key, FG, 100, 50, self.TOP + 400, 1150 + 250 * x)

        mx = len(self.person)
        dx = self.H / mx

        pygame.draw.line(self.screen, FG, (self.MARGIN + self.LEFT, self.MARGIN - 10 + self.TOP),
                         (self.MARGIN + self.LEFT, self.HAUT + self.TOP), 2)

        x_coord = get_scale_value(0, mx, 10)
        for x in x_coord:
            form = str(int(x))
            w = self.data_font.size(form)[0]
            Y = self.HAUT - int(x * dx)
            pygame.draw.line(self.screen, FG, (self.MARGIN + self.LEFT, Y + self.TOP),
                             (self.MARGIN - 5 + self.LEFT, Y + self.TOP), 2)
            self.screen.blit(
                self.data_font.render(form, True, FG),
                ((self.MARGIN - w) + self.LEFT - 10, Y - 10 + self.TOP))


    def mise_a_jour_graphique(self):
        """ Affiche le graphique du pays donné
        ---
        """
        mx = len(self.person)
        my = max(self.y[-1], 1)

        dx = self.H / mx
        dy = self.W / my

        create_mask(self.TOP + self.MARGIN, self.LEFT + self.MARGIN + 2,
                    self.WIDTH - 2 * self.MARGIN, self.HEIGHT - 2 * self.MARGIN, BG, self.screen)
        # Update barre nombres
        create_mask(self.TOP + self.HEIGHT - self.MARGIN + 2, self.LEFT + self.MARGIN - 10,
                    self.WIDTH - self.MARGIN + 10, self.MARGIN, BG, self.screen)

        c_y = [x * dy + self.MARGIN + self.LEFT for x in self.quarantine_time]

        for x in range((len(c_y) + 1) // 2):
            if 2 * x + 1 < len(c_y):
                create_mask(self.TOP + self.MARGIN, c_y[2 * x], c_y[2 * x + 1] - c_y[2 * x], self.HEIGHT - 2 * self.MARGIN, QC, self.screen)
            else:
                create_mask(self.TOP + self.MARGIN, c_y[2 * x], self.LEFT + self.WIDTH - self.MARGIN - c_y[2 * x], self.HEIGHT - 2 * self.MARGIN, QC, self.screen)

        for key in self.data:
            c_x = [(mx - x) * dx + self.MARGIN + self.TOP for x in self.data[key]]
            c_y = [x * dy + self.MARGIN + self.LEFT for x in self.y]
            pts = list(zip(c_y, c_x))
            for x in range(len(pts) - 1):
                pygame.draw.line(self.screen, colors[list(self.data.keys()).index(key)], pts[x], pts[x + 1], 2)

        y_coord = get_scale_value(0, my, 10)
        for y in y_coord:
            X = self.MARGIN + int(y * dy)
            d = str(int(y))
            w, _ = self.font.size(d)
            pygame.draw.line(self.screen, FG, (self.LEFT + X, self.HAUT + self.TOP),
                             (self.LEFT + X, self.DHAUT + self.TOP), 2)
            self.screen.blit(self.data_font.render(d, True, FG), (self.LEFT + X - w // 2 + 7, self.DHAUT + self.TOP))

        pygame.draw.line(self.screen, FG, (self.MARGIN + self.LEFT, self.HAUT + self.TOP),
                         (self.WIDTH - self.MARGIN + 10 + self.LEFT, self.HAUT + self.TOP), 2)


    def mise_a_jour_donnees(self):
        """ Met à jour les données de la simulation
        ---
        """
        self.data["Sains"].append(len(self.sains))
        self.data["Infectés"].append(len(self.infectes))
        self.data["Rétablis"].append(len(self.retablis))


    def reassignation(self):
        """ Assigne les personnes dans leurs compartiments respectifs en fonction de leur état
        ---
        """
        p = 0
        while len(self.infectes) - p > 0:
            if self.infectes[p].etat == Etat.RETABLI:
                self.retablis.append(self.infectes[p])
                self.infectes.pop(p)
            else:
                p += 1
        p = 0
        while len(self.sains) - p > 0:
            if self.sains[p].etat == Etat.INFECTE:
                self.infectes.append(self.sains[p])
                self.sains.pop(p)
            else:
                p += 1


    def afficher(self):
        """ Affiche la simulation
        ---
        """
        create_mask(self.TOP - 50, -20, self.w + 100, self.h + 20, BG, self.screen)
        pygame.draw.line(self.screen, pygame.Color(200, 200, 200), (0, self.TOP - 50), (self.w, self.TOP - 50))
        pygame.draw.line(
            self.screen, pygame.Color(200, 200, 200),
            (self.w, self.TOP - 50),
            (self.w, self.h + self.TOP - 50))
        pygame.draw.line(
            self.screen, pygame.Color(200, 200, 200),
            (self.w, self.h + self.TOP - 50),
            (0, self.h + self.TOP - 50))
        pygame.draw.line(self.screen, pygame.Color(200, 200, 200), (0, self.h + self.TOP - 50), (0, self.TOP - 50))
        [p.afficher(self.screen, self.TOP - 50) for p in self.person]
        # dernière action du tour
        self.y.append(len(self.y))


    def mise_a_jour_texte(self):
        """ Change les chiffres de la simulation
        ---
        """
        if not self.no_action:
            create_mask(self.TOP - 30, 1200, 500, 100, BG, self.screen)
            center_text(self.screen, self.data_font, "Comportement de la population : " + str(self.comportement), FG, 500, 20, self.TOP - 30, 1200)
            center_text(self.screen, self.data_font,
                        f"Taux d'incidence : {self.TAUX_INCIDENCE}", FG, 500, 20, self.TOP, 1200)
        for x, key in enumerate(self.data):
            create_mask(self.TOP + 455, 1150 + 250 * x, 100, 20, BG, self.screen)
            center_text(
                self.screen, self.data_font, str(self.data[key][-1]),
                FG, 100, 20, self.TOP + 455, 1150 + 250 * x)


    def mise_a_jour(self):
        """ Met à jour la simulation
        ---
        """
        for p in self.person:
            p.mise_a_jour(self.w, self.h, self.person)
        for p in self.infectes:
            if random.randint(0, 100) <= p.p * 100:
                for n in self.sains:
                    if p.collision(n):
                        n.etat = Etat.INFECTE
        if len(self.infectes) > 0:
            self.reassignation()
            self.mise_a_jour_comportement()
            self.mise_a_jour_donnees()
            self.mise_a_jour_texte()
            self.mise_a_jour_graphique()
        else:
            if not self.ended:
                self.ended = True
        pygame.display.update()


    def mise_a_jour_comportement(self):
        """ Met à jour le comportement de la simulation
        ---
        """
        if not self.no_action:
            if len(self.infectes) > self.TAUX_INCIDENCE and self.comportement == Comportement.NORMAL:
                self.quarantine_time.append(self.y[-1])
                if self.comportement_urgence == Comportement.QUARANTAINE:
                    self.comportement = Comportement.QUARANTAINE
                    for p in self.person:
                        p.comportement = Comportement.QUARANTAINE
                else:
                    self.comportement = Comportement.CONFINEMENT
                    for p in self.infectes:
                        p.comportement = Comportement.QUARANTAINE
            elif len(self.infectes) < self.TAUX_INCIDENCE * self.threshold and self.comportement == Comportement.QUARANTAINE:
                self.comportement = Comportement.NORMAL
                self.quarantine_time.append(self.y[-1])
                if self.comportement_urgence == Comportement.QUARANTAINE:
                    for p in self.person:
                        p.comportement = Comportement.NORMAL
                else:
                    for p in self.infectes:
                        p.comportement = Comportement.NORMAL


pygame.init()
info = pygame.display.Info()
screen = pygame.display.set_mode((info.current_w, info.current_h), pygame.NOFRAME)
screen.fill(BG)

w = info.current_w // 2 - 10
h = info.current_h - 10


TOP = 50
SAVE = False
NB_SIM = 1

S = 100
NB_PERSON = 1200
THRESHOLD = 0.3


for _ in range(NB_SIM):
    person = []
    for k in range(NB_PERSON):
        v, theta = random.randint(0, 500) / 100, random.randint(0, 628) / 100
        vx, vy = v * math.cos(theta), v * math.sin(theta)
        person.append(
            Person(k,
                random.randint(0, w),
                random.randint(0, h),
                vx, vy, 0, 0, .5, 6))


    Sim = Simulation(person, w, h, screen, TOP, S, THRESHOLD, Comportement.QUARANTAINE)
    Sim.initialisation_affichage()
    x = 0


    if SAVE:
        titre = f"E:\\Python\\Projet\\TIPE\\Modele_epidemiologique\\app\\Simulation\\Taux incidence {S}"
        if not os.path.exists(titre):
            os.makedirs(titre)
        os.chdir(titre)
        data_base = sqlite3.connect("result.db", check_same_thread=False)
        cursor = data_base.cursor()
        l = len(cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'").fetchall())
        cursor.execute(f"""CREATE TABLE IF NOT EXISTS Sim{l} (id integer PRIMARY KEY, {",".join([f'{key} int' for key in Sim.data])})""")


    DATA_SAVED = False

    while not Sim.ended:
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                quit()
        time.sleep(.01)
        Sim.mise_a_jour()
        Sim.afficher()
        if SAVE:
            if not Sim.ended:
                pygame.image.save(screen, f"E:\\Python\\Projet\\TIPE\\Modele_epidemiologique\\app\\Simulation\\Taux incidence {S}\\img{x}.jpg")
            elif not DATA_SAVED:
                for k in range(x):
                    cursor.execute(f"""INSERT INTO Sim{l} VALUES (NULL, {",".join([str(Sim.data[key][k] / NB_PERSON) for key in Sim.data])})""")
                data_base.commit()
                data_base.close()
                DATA_SAVED = True
            x += 1

    titre = f"E:\\Python\\Projet\\TIPE\\Modele_epidemiologique\\app\\Simulation\\Taux incidence {S}"
    if not os.path.exists(titre):
        os.makedirs(titre)
    pygame.image.save(Sim.screen, f"E:\\Python\\Projet\\TIPE\\Modele_epidemiologique\\app\\Simulation\\Taux incidence {S}\\Résultat - Personnes {NB_PERSON}, Comportement {str(Sim.comportement_urgence)}, Threshold {THRESHOLD}.jpg")


# TODO:
#       - pt attractif
#       - afficher reg°
#       - opti° reg°

# pb test
# https://jamanetwork.com/journals/jama/fullarticle/2762130
