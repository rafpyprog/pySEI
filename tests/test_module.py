import os

from pysei import SEI

nu_cpf = os.environ['CPF']
pwd_sei = os.environ['PASSWORD_SEI']

def test_login_sei():
    sei = SEI()
    login_status = sei.login(nu_cpf, pwd_sei)
    assert login_status == True

def test_acessa_tela_pesquisa():
    sei = SEI()
    login_status = sei.login(nu_cpf, pwd_sei)
    sei.acessa_tela_pesquisa()
    assert 'Pesquisar em' in sei.html

def test_pesquisa():
    sei = SEI()
    login_status = sei.login(nu_cpf, pwd_sei)
    query = 'Rafael'
    pesquisa = sei.pesquisa(query)
    assert query in pesquisa.soup.text
