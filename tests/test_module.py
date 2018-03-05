from concurrent.futures import Future, wait
import os
import time

from pysei import SEI, ResultadoPesquisa, ProcessoSei

nu_cpf = os.environ['CPF']
pwd_sei = os.environ['PASSWORD_SEI']


def test_login_sei():
    sei = SEI()
    login_status = sei.login(nu_cpf, pwd_sei)
    assert login_status == True


def test_login_dados_invalidos_sei():
    sei = SEI()
    login_status = sei.login('00000000000', pwd_sei)
    assert login_status == False


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


def test_retorna_resultado_pesquisa():
    sei = SEI()
    sei.login(nu_cpf, pwd_sei)
    p = sei.pesquisa(nu_sei='000000000015500')
    assert isinstance(p, ResultadoPesquisa)


def test_retorna_processo_sei():
    sei = SEI()
    sei.login(nu_cpf, pwd_sei)
    p = sei.pesquisa(nu_sei='103800001719932')
    assert isinstance(p, ProcessoSei)


def test_get_form_url():
    sei = SEI()
    sei.login(nu_cpf, pwd_sei)
    assert sei.form_URL.startswith('https://')


def test_form_url():
    sei = SEI()
    sei.login(nu_cpf, pwd_sei)
    assert sei.form_URL is not None
