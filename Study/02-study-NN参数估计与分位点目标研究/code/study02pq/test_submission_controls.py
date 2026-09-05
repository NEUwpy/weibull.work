import torch
from . import losses as L
from .submission_controls import FeasibleObserver

def test_common_selection_and_multipoint_loss():
    out=torch.tensor([[2.,800.,-.7],[4.,1000.,.3]],dtype=torch.float64,requires_grad=True)
    params=torch.tensor([[2.,1000.,100.],[4.,1000.,500.]],dtype=torch.float64)
    minima=torch.tensor([500.,1200.],dtype=torch.float64)
    p,_=L.build_route_loss('P'); pq,_=L.build_route_loss('P_QSELECT')
    qsel,_=L.build_selection_loss('P_QSELECT')
    torch.testing.assert_close(p(out,params,minima),pq(out,params,minima))
    torch.testing.assert_close(qsel(out,params,minima),L.parameter_target_loss_components(out,params,minima)[0])
    multi,kind=L.build_route_loss('QMULTI')
    expected=sum(L.parameter_target_loss_components(out,params,minima,r)[0] for r in (.9,.95,.99))/3
    torch.testing.assert_close(multi(out,params,minima),expected)
    multi(out,params,minima).backward()
    assert kind=='params' and torch.isfinite(out.grad).all() and (out.grad.abs().sum(0)>0).all()

def test_no_feasible_checkpoint_is_explicit():
    observer=FeasibleObserver(1e-20)
    model=torch.nn.Linear(3,3).double()
    out=torch.zeros((2,3),dtype=torch.float64)
    params=torch.tensor([[2.,1000.,100.],[4.,1000.,500.]],dtype=torch.float64)
    with torch.no_grad():observer(1,model,out,params,torch.tensor([500.,1200.],dtype=torch.float64))
    assert observer.state is None and observer.epoch is None
